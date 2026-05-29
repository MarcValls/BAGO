"""
QMIX trainer for BagoMultiAgentEnv.

Simplified QMIX with:
  - Individual DRQN/MLP per agent
  - Monotonic mixer (similar to VDN with state-based weights)
  - Centralised replay buffer storing full episodes
  - Epsilon-greedy exploration

Dependencies: torch, numpy, pettingzoo
"""

import copy
import json
import random
from collections import deque
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "envs"))

from bago_multi_agent_env import AGENTS, BagoMultiAgentEnv

DEVICE = torch.device("cpu")


class AgentQNet(nn.Module):
    """Individual Q-network for one agent."""

    def __init__(self, obs_dim, action_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, action_dim),
        )

    def forward(self, obs):
        return self.net(obs)


class QMixer(nn.Module):
    """
    Simplified monotonic mixer inspired by QMIX.
    Weights are generated from global state to ensure monotonicity.
    """

    def __init__(self, n_agents, state_dim, embed_dim=32):
        super().__init__()
        self.n_agents = n_agents
        self.hyper_w1 = nn.Linear(state_dim, embed_dim * n_agents)
        self.hyper_b1 = nn.Linear(state_dim, embed_dim)
        self.hyper_w2 = nn.Linear(state_dim, embed_dim)
        self.hyper_b2 = nn.Sequential(
            nn.Linear(state_dim, embed_dim),
            nn.ReLU(),
            nn.Linear(embed_dim, 1),
        )
        self.elu = nn.ELU()

    def forward(self, q_values, state):
        # q_values: (batch, n_agents)
        # state: (batch, state_dim)
        batch_size = q_values.shape[0]
        q_values = q_values.view(batch_size, 1, self.n_agents)

        w1 = torch.abs(self.hyper_w1(state))
        b1 = self.hyper_b1(state)
        w1 = w1.view(batch_size, self.n_agents, -1)
        b1 = b1.view(batch_size, 1, -1)

        hidden = self.elu(torch.bmm(q_values, w1) + b1)

        w2 = torch.abs(self.hyper_w2(state))
        b2 = self.hyper_b2(state)
        w2 = w2.view(batch_size, -1, 1)
        b2 = b2.view(batch_size, 1, 1)

        q_total = torch.bmm(hidden, w2) + b2
        return q_total.view(batch_size)


class EpisodeBuffer:
    """Store full episodes for off-policy QMIX updates."""

    def __init__(self, max_size=5000):
        self.buffer = deque(maxlen=max_size)

    def add(self, episode):
        # episode = dict with keys: obs, action, reward, next_obs, state, next_state, terminated, truncated, mask
        self.buffer.append(episode)

    def sample(self, batch_size):
        return random.sample(self.buffer, min(batch_size, len(self.buffer)))

    def __len__(self):
        return len(self.buffer)


def build_agents(env):
    nets = {}
    target_nets = {}
    optimizers = {}
    for a in AGENTS:
        obs_dim = env.observation_space(a).shape[0]
        act_dim = env.action_space(a).n
        net = AgentQNet(obs_dim, act_dim).to(DEVICE)
        target = copy.deepcopy(net)
        target.eval()
        nets[a] = net
        target_nets[a] = target
        optimizers[a] = optim.Adam(net.parameters(), lr=1e-3)
    return nets, target_nets, optimizers


def get_global_state(env):
    return env.state()


def select_actions(env, obs_dict, nets, epsilon):
    actions = {}
    for a in AGENTS:
        if random.random() < epsilon:
            actions[a] = env.action_space(a).sample()
        else:
            obs_t = torch.FloatTensor(obs_dict[a]).unsqueeze(0).to(DEVICE)
            with torch.no_grad():
                q = nets[a](obs_t)
            actions[a] = int(q.argmax(dim=1).cpu().numpy()[0])
    return actions


def run_episode(env, nets, epsilon):
    obs_dict, info = env.reset(seed=None)
    episode = {k: [] for k in AGENTS}
    states = []
    next_states = []
    terminated = {a: False for a in AGENTS}
    truncated = {a: False for a in AGENTS}

    while env.agents:
        agent = env.agent_selection
        if terminated[agent] or truncated[agent]:
            env.step(None)
            # update dead flags
            terminated = env.terminations.copy()
            truncated = env.truncations.copy()
            continue

        obs = env.observe(agent)
        states.append(get_global_state(env))
        action = select_actions(env, {a: env.observe(a) for a in AGENTS}, nets, epsilon)[agent]
        env.step(action)
        next_obs = env.observe(agent)
        reward = env._cumulative_rewards[agent]
        next_state = get_global_state(env)

        episode[agent].append({
            "obs": obs,
            "action": action,
            "reward": reward,
            "next_obs": next_obs,
            "terminated": env.terminations[agent],
            "truncated": env.truncations[agent],
        })
        next_states.append(next_state)
        terminated = env.terminations.copy()
        truncated = env.truncations.copy()

    # Pad to same length for all agents using the max number of transitions any agent took
    max_len = max(len(episode[a]) for a in AGENTS)
    batch = {}
    for a in AGENTS:
        seq = episode[a]
        pad_len = max_len - len(seq)
        # Pad with zeros / false and mask=0
        for _ in range(pad_len):
            seq.append({
                "obs": np.zeros_like(seq[0]["obs"]) if seq else np.zeros(env.observation_space(a).shape[0]),
                "action": 0,
                "reward": 0.0,
                "next_obs": np.zeros_like(seq[0]["obs"]) if seq else np.zeros(env.observation_space(a).shape[0]),
                "terminated": False,
                "truncated": False,
            })
        batch[a + "_obs"] = np.stack([t["obs"] for t in seq])
        batch[a + "_action"] = np.array([t["action"] for t in seq])
        batch[a + "_reward"] = np.array([t["reward"] for t in seq])
        batch[a + "_next_obs"] = np.stack([t["next_obs"] for t in seq])
        batch[a + "_terminated"] = np.array([t["terminated"] for t in seq])
        batch[a + "_truncated"] = np.array([t["truncated"] for t in seq])
        # mask: 1 for real transitions, 0 for padding
        batch[a + "_mask"] = np.array([1.0] * (max_len - pad_len) + [0.0] * pad_len)

    batch["state"] = np.stack(states + [next_states[-1]] * (max_len - len(states))) if states else np.zeros((max_len, len(get_global_state(env))))
    batch["next_state"] = np.stack(next_states + [next_states[-1]] * (max_len - len(next_states))) if next_states else np.zeros((max_len, len(get_global_state(env))))
    return batch


def train_qmix(env, num_episodes=3000, batch_size=32, gamma=0.99, epsilon_start=1.0, epsilon_end=0.05, epsilon_decay=0.995, target_update=100, save_dir=".bago/rl/checkpoints/qmix"):
    nets, target_nets, optimizers = build_agents(env)
    mixer = QMixer(len(AGENTS), len(get_global_state(env))).to(DEVICE)
    target_mixer = copy.deepcopy(mixer)
    mixer_opt = optim.Adam(mixer.parameters(), lr=1e-3)

    buffer = EpisodeBuffer(max_size=5000)
    epsilon = epsilon_start
    losses = []
    rewards_log = []

    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    for ep in range(num_episodes):
        batch = run_episode(env, nets, epsilon)
        buffer.add(batch)
        # Track episode return (sum of all individual rewards)
        ep_return = sum(batch[a + "_reward"].sum() for a in AGENTS)
        rewards_log.append(ep_return)

        if len(buffer) >= batch_size:
            samples = buffer.sample(batch_size)
            # Stack samples to create training tensors
            max_len = max(s["state"].shape[0] for s in samples)
            
            obs_batch = {}
            next_obs_batch = {}
            action_batch = {}
            reward_batch = {}
            mask_batch = {}
            terminated_batch = {}
            
            for a in AGENTS:
                obs_list = []
                next_obs_list = []
                act_list = []
                rew_list = []
                mask_list = []
                term_list = []
                for s in samples:
                    pad = max_len - s[a + "_obs"].shape[0]
                    if pad > 0:
                        obs_list.append(np.pad(s[a + "_obs"], ((0, pad), (0, 0))))
                        next_obs_list.append(np.pad(s[a + "_next_obs"], ((0, pad), (0, 0))))
                        act_list.append(np.pad(s[a + "_action"], (0, pad)))
                        rew_list.append(np.pad(s[a + "_reward"], (0, pad)))
                        mask_list.append(np.pad(s[a + "_mask"], (0, pad)))
                        term_list.append(np.pad(s[a + "_terminated"].astype(np.float32), (0, pad)))
                    else:
                        obs_list.append(s[a + "_obs"])
                        next_obs_list.append(s[a + "_next_obs"])
                        act_list.append(s[a + "_action"])
                        rew_list.append(s[a + "_reward"])
                        mask_list.append(s[a + "_mask"])
                        term_list.append(s[a + "_terminated"].astype(np.float32))
                obs_batch[a] = torch.FloatTensor(np.stack(obs_list)).to(DEVICE)
                next_obs_batch[a] = torch.FloatTensor(np.stack(next_obs_list)).to(DEVICE)
                action_batch[a] = torch.LongTensor(np.stack(act_list)).to(DEVICE)
                reward_batch[a] = torch.FloatTensor(np.stack(rew_list)).to(DEVICE)
                mask_batch[a] = torch.FloatTensor(np.stack(mask_list)).to(DEVICE)
                terminated_batch[a] = torch.FloatTensor(np.stack(term_list)).to(DEVICE)

            state_list = []
            next_state_list = []
            for s in samples:
                pad = max_len - s["state"].shape[0]
                if pad > 0:
                    state_list.append(np.pad(s["state"], ((0, pad), (0, 0))))
                    next_state_list.append(np.pad(s["next_state"], ((0, pad), (0, 0))))
                else:
                    state_list.append(s["state"])
                    next_state_list.append(s["next_state"])
            state_batch = torch.FloatTensor(np.stack(state_list)).to(DEVICE)
            next_state_batch = torch.FloatTensor(np.stack(next_state_list)).to(DEVICE)

            # Compute Q_values for chosen actions
            q_values = []
            for a in AGENTS:
                q_all = nets[a](obs_batch[a])  # (batch, seq, action_dim)
                q_chosen = q_all.gather(2, action_batch[a].unsqueeze(2)).squeeze(2)  # (batch, seq)
                q_values.append(q_chosen)
            q_values = torch.stack(q_values, dim=2)  # (batch, seq, n_agents)

            # Mixer
            q_total = []
            for t in range(max_len):
                q_t = mixer(q_values[:, t, :], state_batch[:, t, :])
                q_total.append(q_t)
            q_total = torch.stack(q_total, dim=1)  # (batch, seq)

            # Target Q
            with torch.no_grad():
                target_q_values = []
                for a in AGENTS:
                    q_next = target_nets[a](next_obs_batch[a])
                    q_next_max = q_next.max(dim=2)[0]  # (batch, seq)
                    target_q_values.append(q_next_max)
                target_q_values = torch.stack(target_q_values, dim=2)
                target_q_total = []
                for t in range(max_len):
                    qt = target_mixer(target_q_values[:, t, :], next_state_batch[:, t, :])
                    target_q_total.append(qt)
                target_q_total = torch.stack(target_q_total, dim=1)

            # Build target y
            team_reward = torch.stack([reward_batch[a] for a in AGENTS], dim=2).sum(dim=2)  # (batch, seq)
            mask = torch.stack([mask_batch[a] for a in AGENTS], dim=2).min(dim=2)[0]  # (batch, seq)
            terminated_mask = torch.stack([terminated_batch[a] for a in AGENTS], dim=2).max(dim=2)[0]  # (batch, seq)
            y = team_reward + gamma * target_q_total * (1 - terminated_mask)

            loss = ((q_total - y) ** 2 * mask).sum() / mask.sum()

            # Backprop
            for a in AGENTS:
                optimizers[a].zero_grad()
            mixer_opt.zero_grad()
            loss.backward()
            for a in AGENTS:
                optimizers[a].step()
            mixer_opt.step()

            losses.append(float(loss.item()))

        epsilon = max(epsilon_end, epsilon * epsilon_decay)

        if ep % target_update == 0 and ep > 0:
            for a in AGENTS:
                target_nets[a].load_state_dict(nets[a].state_dict())
            target_mixer.load_state_dict(mixer.state_dict())

        if (ep + 1) % 500 == 0:
            mean_reward = float(np.mean(rewards_log[-500:]))
            mean_loss = float(np.mean(losses[-100:])) if losses else 0.0
            print(f"Episode {ep+1}: mean_reward={mean_reward:.3f} epsilon={epsilon:.3f} loss={mean_loss:.4f}")

    # Save
    for a in AGENTS:
        torch.save(nets[a].state_dict(), save_path / f"qnet_{a}.pt")
    torch.save(mixer.state_dict(), save_path / "mixer.pt")
    metrics = {
        "episodes": num_episodes,
        "final_mean_reward": float(np.mean(rewards_log[-500:])),
        "max_reward": float(np.max(rewards_log)),
        "losses_last_100": float(np.mean(losses[-100:])) if losses else 0.0,
    }
    (save_path / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print("QMIX training complete. Saved to", save_path)
    return nets, mixer, metrics


def _self_test():
    env = BagoMultiAgentEnv()
    nets, mixer, metrics = train_qmix(env, num_episodes=200, batch_size=4, target_update=20)
    print("Self-test PASSED — metrics:", metrics)


if __name__ == "__main__":
    _self_test()
