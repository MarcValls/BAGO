"""
BagoMultiAgentEnv — PettingZoo AEC environment for multi-agent RL.

Agents:
  - planner: selects workflow stage and priority
  - executor: selects tool/action within stage
  - validator: checks output quality and emits reward signal
  - recoverer: handles failures (retry/escalate/skip)

Reward model:
  - team_reward: shared sparse reward on episode completion
  - individual_reward: dense reward for each agent's correct action
"""

import numpy as np
from gymnasium import spaces
from pettingzoo.utils.env import AECEnv
from pettingzoo.utils.agent_selector import agent_selector


AGENTS = ["planner", "executor", "validator", "recoverer"]
MAX_STEPS = 15
NUM_TOOLS = 7


class BagoMultiAgentEnv(AECEnv):
    metadata = {"render_modes": ["human"], "name": "bago_multi_agent_v1"}

    def __init__(self, render_mode=None):
        super().__init__()
        self.render_mode = render_mode
        self.possible_agents = AGENTS[:]
        self.agent_name_mapping = {a: i for i, a in enumerate(AGENTS)}

        # Observations: each agent sees a subset + common state
        self.observation_spaces = {
            a: spaces.Box(low=0.0, high=1.0, shape=(20,), dtype=np.float32)
            for a in AGENTS
        }
        self.action_spaces = {
            "planner": spaces.Discrete(5),   # stage priorities
            "executor": spaces.Discrete(NUM_TOOLS),
            "validator": spaces.Discrete(3),  # pass/warn/fail
            "recoverer": spaces.Discrete(4),  # retry/escalate/skip/abort
        }

        # Init dummy state so state() works before reset
        self.step_count = 0
        self.stage_id = 0
        self.last_tool = -1
        self.last_quality = 0.5
        self.error_history = [0.0]
        self.budget_left = 1.0
        self.done = False
        self.actions_log = []

    def _get_obs(self, agent):
        # Common state: step_progress(1), stage_id(1), last_tool(1), last_quality(1),
        # errors(4), budget_left(1), retries(1), completion(1)
        base = np.zeros(10, dtype=np.float32)
        base[0] = self.step_count / MAX_STEPS
        base[1] = self.stage_id / 4.0
        base[2] = (self.last_tool + 1) / NUM_TOOLS
        base[3] = self.last_quality
        for i, e in enumerate(self.error_history[-4:]):
            base[4 + i] = e
        base[8] = self.budget_left
        base[9] = 1.0 if self.done else 0.0

        # Agent-specific one-hot
        agent_vec = np.zeros(4, dtype=np.float32)
        agent_vec[self.agent_name_mapping[agent]] = 1.0

        # Role-specific context
        role = np.zeros(6, dtype=np.float32)
        if agent == "planner":
            role[0] = self.stage_id / 4.0
            role[1] = sum(self.error_history) / max(len(self.error_history), 1)
        elif agent == "executor":
            role[2] = self.last_quality
            role[3] = self.budget_left
        elif agent == "validator":
            role[4] = self.last_quality
        elif agent == "recoverer":
            role[5] = sum(self.error_history) / max(len(self.error_history), 1)

        return np.concatenate([base, agent_vec, role]).astype(np.float32)

    def reset(self, seed=None, options=None):
        if seed is not None:
            np.random.seed(seed)
        self.step_count = 0
        self.stage_id = 0
        self.last_tool = -1
        self.last_quality = 0.5
        self.error_history = [0.0]
        self.budget_left = 1.0
        self.done = False
        self.actions_log = []

        self.agents = self.possible_agents[:]
        self.rewards = {a: 0.0 for a in self.agents}
        self._cumulative_rewards = {a: 0.0 for a in self.agents}
        self.terminations = {a: False for a in self.agents}
        self.truncations = {a: False for a in self.agents}
        self.infos = {a: {} for a in self.agents}
        self.observations = {a: self._get_obs(a) for a in self.agents}
        self.num_moves = 0

        self._agent_selector = agent_selector(self.agents)
        self.agent_selection = self._agent_selector.next()
        return self.observations, self.infos

    def observe(self, agent):
        return self._get_obs(agent)

    def state(self):
        # Global state for centralised critic / QMIX mixer
        return np.concatenate([self._get_obs(a) for a in self.possible_agents]).astype(np.float32)

    def step(self, action):
        agent = self.agent_selection
        if self.terminations[agent] or self.truncations[agent]:
            self._was_dead_step(action)
            return

        self._clear_rewards()
        self._cumulative_rewards[agent] = 0.0
        self.actions_log.append((agent, int(action)))

        # Simulate dynamics based on agent role
        reward = 0.0
        if agent == "planner":
            desired = self.stage_id
            if action == desired:
                reward = 0.2
                self.stage_id = min(self.stage_id + 1, 4)
            else:
                reward = -0.1
                self.budget_left -= 0.05
        elif agent == "executor":
            self.last_tool = action
            if action < 4:
                self.last_quality = np.random.uniform(0.6, 1.0)
                reward = 0.15
            else:
                self.last_quality = np.random.uniform(0.0, 0.5)
                reward = -0.05
                self.error_history.append(1.0)
            self.budget_left -= 0.03
        elif agent == "validator":
            if action == 0 and self.last_quality >= 0.7:
                reward = 0.2
            elif action == 2 and self.last_quality < 0.5:
                reward = 0.2
            elif action == 1:
                reward = 0.05
            else:
                reward = -0.1
        elif agent == "recoverer":
            if self.last_quality < 0.5:
                if action == 0:
                    reward = 0.1
                    self.last_quality = np.random.uniform(0.5, 0.9)
                elif action == 1:
                    reward = 0.05
                elif action == 2:
                    reward = -0.05
                else:
                    reward = -0.2
                    self.done = True
            else:
                if action == 2:
                    reward = 0.05
                else:
                    reward = -0.02

        self.step_count += 1
        team_bonus = 0.0
        if self.stage_id >= 4 and self.last_quality >= 0.7 and not self.done:
            team_bonus = 1.0
            self.done = True

        # Truncate all if max steps reached
        if self.step_count >= MAX_STEPS:
            for a in self.agents:
                if not self.terminations[a]:
                    self.truncations[a] = True

        # Only assign rewards to agents that were alive BEFORE this step
        alive = [a for a in self.agents if not (self.terminations[a] or self.truncations[a])]
        if agent in alive:
            self.rewards[agent] = reward + team_bonus
            self.infos[agent]["team_bonus"] = float(team_bonus)

        if team_bonus > 0:
            for other in alive:
                if other != agent:
                    self.rewards[other] += 0.3 * team_bonus
                    self.infos[other]["team_bonus"] = float(0.3 * team_bonus)

        # Mark all done if workflow completed
        if self.done:
            for a in self.agents:
                if not self.truncations[a]:
                    self.terminations[a] = True

        self._accumulate_rewards()

        if self._agent_selector.is_last():
            self.num_moves += 1

        self.agent_selection = self._agent_selector.next()

    def render(self):
        if self.render_mode == "human":
            print(f"Step {self.step_count} | Stage {self.stage_id} | Quality {self.last_quality:.2f} | Budget {self.budget_left:.2f}")
            for a, r in self.rewards.items():
                print(f"  {a}: reward={r:.3f}")

    def observation_space(self, agent):
        return self.observation_spaces[agent]

    def action_space(self, agent):
        return self.action_spaces[agent]

    def close(self):
        pass

    def _clear_rewards(self):
        for a in self.agents:
            self.rewards[a] = 0.0


def api_test():
    from pettingzoo.test import api_test as _api_test
    env = BagoMultiAgentEnv()
    _api_test(env, num_cycles=50)
    print("PettingZoo api_test PASSED")


def _self_test():
    env = BagoMultiAgentEnv()
    obs, info = env.reset(seed=42)
    total_rewards = {a: 0.0 for a in AGENTS}
    for _ in range(50):
        agent = env.agent_selection
        action = env.action_space(agent).sample()
        env.step(action)
        total_rewards[agent] += env.rewards[agent]
        if all(env.terminations.values()) or all(env.truncations.values()):
            break
    print("Self-test PASSED — total rewards:", total_rewards)


if __name__ == "__main__":
    _self_test()
    api_test()
