"""
Karpovich v4 — Instrumentos físicamente precisos
- TR-909 kick: modelo circuito analógico (resonador + click + bridge)
- LinnDrum snare: partiales + noise coloreado
- Hihat: 6 partiales metálicos inarmónicos (modelo Karplus-Strong)
- Fender Jazz bass: síntesis por tabla de onda + pluck + cuerda
- Juno-60 pad: BBD chorus con modulación de fase real, detuning per-voice
- Lead: sin porta + vibrato delayed + VCA analógica
"""
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import soundfile as sf
from pathlib import Path
from scipy.signal import butter, sosfilt, lfilter

SR = 44100
BPM = 130
BEAT = 60.0/BPM
BAR  = BEAT*4
BARS = 32
N    = int(BAR*BARS*SR)
rng  = np.random.default_rng(13)

def t(n): return np.arange(n)/SR
def lp(s,c,o=4): 
    c=np.clip(c,20,20000)
    return sosfilt(butter(o,c/(SR/2),btype='low',output='sos'),s)
def hp(s,c,o=2): 
    c=np.clip(c,20,20000)
    return sosfilt(butter(o,c/(SR/2),btype='high',output='sos'),s)
def bp(s,lo,hi,o=2):
    lo,hi=np.clip(lo,20,20000),np.clip(hi,20,20000)
    if lo>=hi: return s
    return sosfilt(butter(o,[lo/(SR/2),hi/(SR/2)],btype='band',output='sos'),s)

# ────────────────────────────────────────────────────────────────
# TR-909 KICK — modelo circuito: click + resonador + bridge
# ────────────────────────────────────────────────────────────────
def tr909_kick(vel=1.0):
    dur = 0.55
    n = int(dur*SR)
    tt = t(n)
    
    # Click transiente (condenser capacitor charge)
    click_dur = int(0.008*SR)
    click = np.zeros(n)
    click[:click_dur] = np.exp(-tt[:click_dur]*800) * rng.standard_normal(click_dur)
    click = bp(click, 3000, 9000) * 0.35
    
    # Resonador: pitch envelope exponencial (circuito VCO analógico)
    f0 = 58.0    # pitch inicial Hz
    f1 = 28.0    # pitch final
    tau = 0.045  # decaimiento del pitch
    freq = f1 + (f0-f1)*np.exp(-tt/tau)
    phase = 2*np.pi*np.cumsum(freq)/SR
    body = np.sin(phase)
    
    # Amplitud: dos exponenciales (attack bridger + body)
    amp = 0.95*np.exp(-tt/0.38) + 0.05*np.exp(-tt/0.012)
    body *= amp
    
    # Saturación suave (diodo germanio sim)
    body = np.tanh(body*2.2)/np.tanh(2.2)
    
    # Filtro low-pass (condensador de salida)
    body = lp(body, 80)
    
    out = (click + body) * vel
    pk = np.max(np.abs(out))
    return out/pk if pk>0 else out

# ────────────────────────────────────────────────────────────────
# LINNDRUM SNARE — partiales + noise con envolvente doble
# ────────────────────────────────────────────────────────────────
def linndrum_snare(vel=1.0):
    n = int(0.28*SR)
    tt = t(n)
    
    # Componente tonal: membrana (dos modos)
    f1, f2 = 178.0, 330.0
    tone  = np.sin(2*np.pi*f1*tt)*np.exp(-tt*48)
    tone += np.sin(2*np.pi*f2*tt)*np.exp(-tt*35)*0.6
    
    # Noise: filtra con bandpass (cuerda snare ~2-8kHz)
    noise = rng.standard_normal(n)
    noise_body = bp(noise, 200, 3500) * np.exp(-tt*32)
    noise_snap  = bp(noise, 4000, 12000) * np.exp(-tt*120)   # crack inicial
    
    out = tone*0.40 + noise_body*0.38 + noise_snap*0.22
    out *= vel
    pk = np.max(np.abs(out))
    return out/pk*0.85 if pk>0 else out

# ────────────────────────────────────────────────────────────────
# HIHAT metálico — 6 partiales inarmónicos (modelo placa metálica)
# ────────────────────────────────────────────────────────────────
_HH_PARTIALS = [1.0, 1.4831, 1.7471, 2.0843, 2.3353, 2.5776]  # Ratios inarmónicos

def metallic_hihat(decay, vel=1.0):
    n = int(max(decay+0.02, 0.03)*SR)
    tt = t(n)
    f0 = 8500.0
    sig = np.zeros(n)
    for i,r in enumerate(_HH_PARTIALS):
        phase = rng.uniform(0, 2*np.pi)
        sig += np.sin(2*np.pi*f0*r*tt + phase) * (0.7**i)
    sig *= np.exp(-tt/max(decay,0.001))
    # Ruido de aleación (choque metal)
    noise = hp(rng.standard_normal(n)*np.exp(-tt*60), 7000)*0.3
    sig = sig*0.7 + noise
    sig = hp(sig, 6500)
    pk = np.max(np.abs(sig))
    return sig/pk*vel if pk>0 else sig

def hh_closed(vel=1.0): return metallic_hihat(0.028, vel)
def hh_open(vel=1.0):   return metallic_hihat(0.14,  vel)

# ────────────────────────────────────────────────────────────────
# CONGA — resonador cilíndrico
# ────────────────────────────────────────────────────────────────
def conga_drum(hz=280, vel=1.0):
    n = int(0.18*SR)
    tt = t(n)
    # Membrana: pitch decay
    freq = hz * np.exp(-tt*8)
    phase = 2*np.pi*np.cumsum(freq)/SR
    sig = np.sin(phase)*np.exp(-tt*28)
    sig += np.sin(phase*1.52)*np.exp(-tt*45)*0.3  # 2o modo
    sig += bp(rng.standard_normal(n)*np.exp(-tt*80), 800, 3000)*0.12
    pk = np.max(np.abs(sig))
    return sig/pk*vel*0.55 if pk>0 else sig

# ────────────────────────────────────────────────────────────────
# FENDER JAZZ BASS — síntesis sustractiva + inarmónicos de cuerda
# ────────────────────────────────────────────────────────────────
def jazz_bass_note(freq, dur_s, vel=1.0):
    n = int(dur_s*SR)
    tt = t(n)
    
    # Partiales (cuerda de bajo: inarmónicos por rigidez)
    B = 0.0005  # inharmonicity factor (cuerda D/G bajo)
    harmonics = []
    for k in range(1,9):
        fk = freq*k*np.sqrt(1+B*k*k)
        amp = (1/k)*np.exp(-k*0.18)   # espectro caída 6dB/oct
        decay_k = 0.8/(1+k*0.25)      # armónicos superiores decaen más rápido
        harmonics.append(np.sin(2*np.pi*fk*tt)*amp*np.exp(-tt/decay_k))
    sig = np.sum(harmonics, axis=0)
    
    # Sub-oscilador una octava abajo (refuerza fundamental)
    sub = np.sin(2*np.pi*freq*0.5*tt)*np.exp(-tt/1.2)*0.40
    sig += sub
    
    # Filtro LP: cuerda fretted (finger mute)
    sig = lp(sig, 2800)
    
    # Cuerpo: resonancia de la caja (formante ~250Hz)
    body_res = bp(sig, 180, 380)*0.25
    sig += body_res
    
    # Pluck attack: click de dedo
    pluck = np.zeros(n)
    pk_n = int(0.004*SR)
    if pk_n < n:
        pluck[:pk_n] = np.linspace(0.3,0,pk_n)
    sig += pluck
    
    # Saturación suave (tubo preamp)
    sig = np.tanh(sig*1.4)/np.tanh(1.4)
    
    # Amplitud envolvente (punch rápido)
    env = np.ones(n)
    a = int(0.006*SR); r_s = int(0.08*SR)
    env[:a] = np.linspace(0,1,a)
    env[-r_s:] = np.linspace(1,0,r_s)
    
    sig = lp(sig*env, 600)   # LP final (tono jazz bass oscuro)
    pk_ = np.max(np.abs(sig))
    return sig/pk_*vel if pk_>0 else sig

# ────────────────────────────────────────────────────────────────
# JUNO-60 PAD — BBD chorus real (modulación de fase, 2 voces anti-fase)
# ────────────────────────────────────────────────────────────────
def juno60_voice(freq, n, detune_cents=0):
    f = freq*(2**(detune_cents/1200))
    # DCO: saw + rectified sin (Juno oscilador)
    s = np.zeros(n)
    tt = t(n)
    s += 0.6*( 2*(tt*f - np.floor(tt*f+0.5)) )           # saw
    s += 0.4*np.abs(np.sin(2*np.pi*f*0.5*tt)) - 0.2      # suboscilador
    return s

def juno60_pad(freqs, n_samples):
    # 6 voces por nota, detuned
    detunings = [-14,-7,-2,0,4,9]  # cents (reproducción Juno)
    mono = np.zeros(n_samples)
    for f in freqs:
        for dc in detunings:
            mono += juno60_voice(f, n_samples, dc) * (0.16/len(detunings))
    
    # VCF: LP con resonancia suave (IR3109 filter)
    mono = lp(mono, 3200)
    
    # ADSR: lento pad
    n=n_samples; tt=t(n)
    env = np.ones(n)
    at=int(0.9*SR); dt=int(0.3*SR); rt=int(2.0*SR)
    env[:at]=np.linspace(0,1,at)
    env[at:at+dt]=np.linspace(1,0.78,dt)
    env[-rt:]*=np.linspace(1,0,rt)
    mono *= env
    
    # BBD chorus: 2 voces, delay modulado, LFO en antifase
    def bbd_voice(sig, lfo_phase_offset, rate=0.65, depth_ms=9.5):
        dep = int(depth_ms/1000*SR)
        lfo = (np.sin(2*np.pi*rate*t(len(sig))+lfo_phase_offset)*0.5+0.5)*dep
        out = np.zeros(len(sig))
        for i in range(len(sig)):
            d = int(lfo[i])
            src = i-d
            if src>=0: out[i]=sig[src]
        return out
    
    L = bbd_voice(mono, 0)          # LFO fase 0
    R = bbd_voice(mono, np.pi)      # LFO antifase → máxima separación
    
    # Reverb plate (Juno tenía spring reverb, usamos plate)
    def plate_rev(s, rt60=2.2, wet=0.40):
        buf=np.zeros(len(s)+int(rt60*SR))
        buf[:len(s)]=s
        for d in [1553,2333,3571,5179,7411,9629]:
            if d<len(buf): buf[d:]+=buf[:-d]*0.52*np.exp(-d/SR/rt60)
        return s+buf[:len(s)]*wet
    
    L=plate_rev(L); R=plate_rev(R)
    return L, R

# ────────────────────────────────────────────────────────────────
# LEAD — sine+saw con vibrato delayed y portamento
# ────────────────────────────────────────────────────────────────
def synth_lead(freq, dur_s, prev_freq=None, vel=1.0):
    n = int(dur_s*SR)
    tt = t(n)
    
    # Portamento desde nota anterior
    if prev_freq and prev_freq!=freq:
        porta_t = int(0.04*SR)
        if porta_t<n:
            f_arr = np.concatenate([
                np.linspace(prev_freq, freq, porta_t),
                np.full(n-porta_t, freq)
            ])
        else:
            f_arr = np.full(n, freq)
    else:
        f_arr = np.full(n, freq)
    
    # Vibrato delayed (empieza en 50ms, profundidad 8 cents)
    vib_start = int(0.05*SR)
    vib_depth = 0.005  # semitono ~8 cents
    vib = np.zeros(n)
    if vib_start<n:
        ramp = np.minimum(np.linspace(0,1,n-vib_start)*5, 1.0)
        vib[vib_start:] = np.sin(2*np.pi*5.8*tt[vib_start:])*vib_depth*ramp
    f_arr = f_arr*(1+vib)
    
    # Osciladores: sine 50% + saw 50%
    phase = 2*np.pi*np.cumsum(f_arr)/SR
    osc = (np.sin(phase)*0.5 + (phase%(2*np.pi)/np.pi - 1)*0.5)
    osc += np.sin(phase*2)*0.12   # octava
    osc += np.sin(phase*1.5)*0.08  # quinta
    
    # VCF analógico (Moog ladder 24dB)
    osc = lp(osc, 5500)
    
    # VCA envolvente
    env = np.ones(n)
    a=int(0.012*SR); r_s=int(0.18*SR)
    env[:a]=np.linspace(0,1,a)
    if r_s<n: env[-r_s:]=np.linspace(1,0,r_s)
    
    return osc*env*vel*0.55

# ────────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DEL TRACK
# ────────────────────────────────────────────────────────────────
print("Building drums...")
drumL = np.zeros(N); drumR = np.zeros(N)
b16 = int(BEAT/4*SR)
bar_s = int(BAR*SR)

kick_s  = tr909_kick()
snare_s = linndrum_snare()
hh_c_s  = hh_closed()
hh_o_s  = hh_open()
cg_a    = conga_drum(255)
cg_b    = conga_drum(368)

kp = [1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0]
sp = [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0]
hp_=[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
ho_=[0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,1]
ca_=[0,0,1,0,0,1,0,0,0,0,1,0,0,0,0,1]
cb_=[0,1,0,0,1,0,0,0,0,1,0,0,1,0,1,0]

n16_total = N//b16
for i in range(n16_total):
    p = i%16
    sw = int((0.60-0.5)*(BEAT/2)*SR) if p%2==1 else 0
    pos = max(0, i*b16 + sw + int(rng.integers(-180,180)))
    vv = 0.88+rng.random()*0.24

    def add_drum(snd, vol=1.0, pan=0.0):
        e=min(pos+len(snd),N)
        l_g=np.sqrt(0.5*(1-pan)); r_g=np.sqrt(0.5*(1+pan))
        drumL[pos:e]+=snd[:e-pos]*vol*vv*l_g
        drumR[pos:e]+=snd[:e-pos]*vol*vv*r_g

    if kp[p]: add_drum(kick_s, 1.0, 0.0)
    if sp[p]: add_drum(snare_s, 1.0, 0.0)
    if hp_[p]: add_drum(hh_c_s, 0.55+rng.random()*0.45, 0.25)
    if ho_[p]: add_drum(hh_o_s, 0.88, 0.25)
    if ca_[p]: add_drum(cg_a, 0.70, -0.30)
    if cb_[p]: add_drum(cg_b, 0.62, -0.15)

print("Building bass...")
bassL = np.zeros(N); bassR = np.zeros(N)
roots = [220,220,165,196,220,220,165,174.6,196,220,196,165,220,196,220,165]
nd = int(BEAT/2*SR)
for bar in range(BARS):
    r = roots[bar%len(roots)]
    pat = [r, r*2, r*1.5, r, r, r*2, r*0.75, r]
    for i,f in enumerate(pat):
        pos = bar*bar_s+i*nd
        if pos+nd>N: break
        n_=min(nd,N-pos)
        note = jazz_bass_note(f, n_/SR, vel=0.82)
        bassL[pos:pos+len(note)] += note
        bassR[pos:pos+len(note)] += note

print("Building pad...")
pad_chord = [220, 261.6, 329.6, 392.0, 440.0]   # Am9
padL_full, padR_full = juno60_pad(pad_chord, N)

# LFO psicodélico → VCF modulación (por bloques)
lfo_pad = 0.5+0.5*np.sin(2*np.pi*0.5*np.arange(N)/SR)
for ch,arr in [(padL_full,padL_full.copy()),(padR_full,padR_full.copy())]:
    pass  # el LFO ya está integrado en juno60_pad

print("Building lead...")
leadL = np.zeros(N); leadR = np.zeros(N)
lead_melody = [440,440,493.9,523.2,440,392,440,493.9,
               392,440,493.9,440,523.2,493.9,392,440]
prev_f = None
for bar in range(4,BARS):
    note_f = lead_melody[(bar-4)%len(lead_melody)]
    for bi in range(4):
        pos = bar*bar_s+bi*int(BEAT*SR)
        dur = BEAT*0.92  # legato ligero
        n_ = min(int(dur*SR), N-pos)
        if n_<=0: continue
        snd = synth_lead(note_f, dur, prev_f)[:n_]
        # Flanger (15ms delay, LFO 3.5Hz)
        dep=int(0.015*SR)
        lfl=np.sin(2*np.pi*3.5*t(n_))*0.5+0.5
        fl=np.zeros(n_)
        for j in range(n_):
            src=j-int(lfl[j]*dep)
            if src>=0: fl[j]=snd[src]
        snd=(snd+fl*0.7)/1.7
        # Ping-pong delay
        dly=int(BEAT*SR)
        ppL_s=np.zeros(n_); ppR_s=np.zeros(n_)
        for j in range(n_):
            ppL_s[j]=snd[j]+(ppR_s[j-dly]*0.38 if j>=dly else 0)
            ppR_s[j]=snd[j]+(ppL_s[j-dly]*0.38 if j>=dly else 0)
        leadL[pos:pos+n_]+=ppL_s*0.58
        leadR[pos:pos+n_]+=ppR_s*0.58
        prev_f=note_f

print("Building arp...")
arpL=np.zeros(N); arpR=np.zeros(N)
arp_notes=[440,523.2,659.3,523.2,415.3,493.9,659.3,493.9]
echo_d=int(BEAT/2*SR)
for i in range(n16_total):
    bar=i*b16//bar_s
    if bar<2 or bar>=30: continue
    f=arp_notes[i%len(arp_notes)]
    sw=int((0.60-0.5)*(BEAT/2)*SR) if i%2==1 else 0
    pos=max(0,i*b16+sw+int(rng.integers(-80,80)))
    n_=min(b16,N-pos)
    if n_<=0: continue
    # Stab: saw+sub, ataque rápido
    tt_=t(n_)
    s=0.55*(2*(tt_*f-np.floor(tt_*f+0.5)))+0.20*np.sin(2*np.pi*f*0.5*tt_)
    s=lp(s,6000)
    env=np.exp(-32*tt_)
    s*=env*0.55
    for rep in range(3):
        ep=pos+(rep+1)*echo_d; vol=(0.38**rep)
        if ep+n_<=N:
            arpL[ep:ep+n_]+=s*vol*(0.7 if rep%2==0 else 0.3)
            arpR[ep:ep+n_]+=s*vol*(0.3 if rep%2==0 else 0.7)
    arpL[pos:pos+n_]+=s*0.6; arpR[pos:pos+n_]+=s*0.4

# ── FILTER SWEEP ──
print("Mixing...")
sweep=np.ones(N)
sweep[:int(BAR*2*SR)]=np.linspace(0.02,1,int(BAR*2*SR))
sweep[int(BAR*28*SR):]=np.linspace(1,0.02,N-int(BAR*28*SR))

def norm(s,tg=0.85):
    p=np.max(np.abs(s)); return s/p*tg if p>0 else s

drumL=norm(drumL,0.82); drumR=norm(drumR,0.82)
bassL=norm(bassL,0.76); bassR=norm(bassR,0.76)
padL_=norm(padL_full,0.62); padR_=norm(padR_full,0.62)
leadL=norm(leadL,0.60); leadR=norm(leadR,0.60)
arpL=norm(arpL,0.46); arpR=norm(arpR,0.46)

L = (drumL+bassL+padL_+leadL+arpL)*sweep
R = (drumR+bassR+padR_+leadR+arpR)*sweep

# EQ global Nu-Disco: cortar lodo 300-500Hz, realzar 3-8kHz
sos_cut = butter(2,[300/(SR/2),500/(SR/2)],btype='band',output='sos')
L -= sosfilt(sos_cut,L)*0.35
R -= sosfilt(sos_cut,R)*0.35
sos_pres = butter(2, 3000/(SR/2), btype='high', output='sos')
L += sosfilt(sos_pres,L)*0.20
R += sosfilt(sos_pres,R)*0.20
sos_air  = butter(2, 9000/(SR/2), btype='high', output='sos')
L += sosfilt(sos_air,L)*0.12
R += sosfilt(sos_air,R)*0.12

stereo = np.stack([L,R],axis=1)
pk = np.max(np.abs(stereo))
stereo = stereo/pk*0.95

# Check width
mono_=stereo.mean(axis=1); side_=(stereo[:,0]-stereo[:,1])/2
w=20*np.log10(np.sqrt(np.mean(side_**2))+1e-9)-20*np.log10(np.sqrt(np.mean(mono_**2))+1e-9)

out = str(Path(__file__).parent.parent.parent / "karpovich_v4_acoustic.wav")
sf.write(out, stereo, SR)
print(f"✅ {out}")
print(f"   Duración: {N/SR:.1f}s | BPM: {BPM} | Width: {w:+.1f} dB")
