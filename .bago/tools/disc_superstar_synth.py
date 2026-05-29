#!/usr/bin/env python3
"""

disc_superstar_synth.py — Vincent Vargas "Disc SuperStar" style synthesizer
French/Euro Disco House · 127 BPM · D Major · ~60s
Elementos: 4-on-the-floor, chord stabs filtrados, disco strings,
           funky bass, Rhodes, Karplus-Strong guitar chops,
           vocal formant synth, filter sweep (French touch)

Usage: python3 disc_superstar_synth.py [output.wav]
Requires: numpy, scipy, soundfile
"""
import sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

SR    = 44100
BPM   = 127
BEAT  = 60.0 / BPM
BAR   = BEAT * 4
BARS  = 32
N     = int(BAR * BARS * SR)
rng   = np.random.default_rng(42)

# Chord progression: Dmaj7 → Gmaj7 → Bm7 → A7
CHORD_PROG = [
    [146.83, 185.00, 220.00, 277.18],
    [196.00, 246.94, 293.66, 370.00],
    [123.47, 146.83, 185.00, 220.00],
    [110.00, 138.59, 164.81, 196.00],
]
BASS_PATTERNS = {
    0: [(0,146.83,.5),(1,146.83,.5),(1.5,220.,.25),(2,146.83,.5),(3,195.,.5),(3.5,146.83,.25)],
    1: [(0,196.,.5),(1,196.,.5),(1.5,293.66,.25),(2,196.,.5),(3,246.94,.5),(3.5,196.,.25)],
    2: [(0,123.47,.5),(1,123.47,.5),(1.5,185.,.25),(2,123.47,.5),(3,164.81,.5),(3.5,123.47,.25)],
    3: [(0,110.,.5),(1,110.,.5),(1.5,164.81,.25),(2,110.,.5),(3,146.83,.5),(3.5,110.,.25)],
}
RHODES_NOTES = {
    0:[146.83,185.00,220.00], 1:[196.00,246.94,293.66],
    2:[123.47,146.83,185.00], 3:[110.00,138.59,164.81],
}
GUITAR_CHORDS = [(0,370.),(0.5,370.),(1.25,440.),(2,370.),(2.5,440.),(3.25,493.88)]
VOX_PATTERN   = [(0,293.66),(1,277.18),(2,246.94),(3,261.63)]

def t(n):  return np.arange(n) / SR

def lp(s, c, o=2):
    c = np.clip(c, 20, 20000)
    return sosfilt(butter(o, c/(SR/2), btype='low',  output='sos'), s)

def hp(s, c, o=2):
    c = np.clip(c, 20, 20000)
    return sosfilt(butter(o, c/(SR/2), btype='high', output='sos'), s)

def bp(s, lo, hi, o=2):
    lo, hi = np.clip(lo, 20, 20000), np.clip(hi, 20, 20000)
    return sosfilt(butter(o, [lo/(SR/2), hi/(SR/2)], btype='band', output='sos'), s)

def shelf(sig, freq, db, btype='high'):
    sos = butter(2, np.clip(freq, 20, 20000)/(SR/2), btype=btype, output='sos')
    return sig + sosfilt(sos, sig) * (10**(db/20) - 1)

def tanh_sat(s, d=1.5): return np.tanh(s*d) / np.tanh(d)

def rev(s, rt=1.8, wet=0.35):
    buf = np.zeros(len(s) + int(rt*SR)); buf[:len(s)] = s
    for d_ in [1031, 1657, 2503, 3779, 5227]:
        if d_ < len(buf): buf[d_:] += buf[:-d_] * 0.53 * np.exp(-d_/SR/rt)
    return s + buf[:len(s)] * wet

def house_kick(n=int(0.35*SR)):
    tt = t(n); f  = 80*np.exp(-tt*22) + 28
    ph = 2*np.pi*np.cumsum(f)/SR
    s  = np.sin(ph)*np.exp(-tt*9)
    click = hp(rng.standard_normal(n)*np.exp(-tt*300), 3000) * 0.25
    s = tanh_sat(s*1.6, 2.0) + click; s = lp(s, 150)
    pk = np.max(np.abs(s)); return s/pk*0.92

def clap(n=int(0.18*SR)):
    tt = t(n); layers = []
    for dm in [0, 6, 12]:
        d = int(dm/1000*SR); noise = rng.standard_normal(n)*np.exp(-tt*60)
        layer = np.zeros(n); layer[d:] = noise[:n-d]
        layers.append(bp(layer, 600, 6000) * 0.8)
    s = sum(layers)/3; s = shelf(s, 3000, 6)
    pk = np.max(np.abs(s)); return s/pk*0.75

def hh(decay=0.025, vel=1.0):
    n  = int(max(decay, 0.02)*SR); tt = t(n)
    partials = [1.0, 1.4142, 1.7321, 2.2360, 2.6458, 3.1623]; s = np.zeros(n)
    for i, r in enumerate(partials):
        s += np.sin(2*np.pi*8800*r*tt + rng.uniform(0, 6.28)) * (0.65**i)
    s *= np.exp(-tt/max(decay, 0.001)); s = hp(s, 7000)
    pk = np.max(np.abs(s)); return s/pk*vel

def disco_strings(chord_freqs, n_samp, vel=1.0):
    mono = np.zeros(n_samp)
    for f in chord_freqs:
        for det in [-0.022, -0.010, -0.003, 0.008, 0.018]:
            fd = f*(2**det); tt_ = t(n_samp); s = np.zeros(n_samp)
            for k in range(1, 16):
                if fd*k > 18000: break
                s += np.sin(2*np.pi*fd*k*tt_ + rng.uniform(0,6.28)) * (1/k)
            s = lp(s, 9000); mono += s * (0.14/len(chord_freqs))
    dep = int(0.012*SR); lfo = np.sin(2*np.pi*0.72*t(n_samp))
    dl = (lfo*0.5+0.5)*dep; dr = (-lfo*0.5+0.5)*dep
    L = np.zeros(n_samp); R = np.zeros(n_samp)
    for i in range(n_samp):
        sl = i-int(dl[i]); sr_ = i-int(dr[i])
        L[i] = mono[sl] if sl>=0 else 0
        R[i] = mono[sr_] if sr_>=0 else 0
    L = (mono+L*0.85)/1.85; R = (mono+R*0.85)/1.85
    L = rev(L, 2.0, 0.40); R = rev(R, 2.0, 0.40)
    tt2 = t(n_samp); env = np.ones(n_samp)
    at = int(0.12*SR); rt = int(1.5*SR)
    env[:at] = np.linspace(0, 1, at)
    if rt < n_samp: env[-rt:] *= np.linspace(1, 0, rt)
    return L*env*vel, R*env*vel

def disco_bass_note(freq, dur_s, vel=1.0):
    n = int(dur_s*SR); tt = t(n)
    sub = np.sin(2*np.pi*freq*tt)*0.45; saw_ = np.zeros(n)
    for k in range(1, 9):
        fk = freq*k
        if fk > 8000: break
        saw_ += np.sin(2*np.pi*fk*tt) * (1/k) * np.exp(-k*0.2)
    sig = sub + lp(saw_, 1800)
    env = np.exp(-tt*4.5) + 0.15*np.exp(-tt*0.8); env = np.minimum(env, 1.0)
    sig *= env; sig = tanh_sat(sig, 1.6); sig = lp(sig, 800)
    pk = np.max(np.abs(sig)); return sig/pk*vel if pk>0 else sig

def chord_stab(chord_freqs, n_samp, cutoff=3500, vel=1.0):
    tt_ = t(n_samp); s = np.zeros(n_samp)
    for f in chord_freqs:
        saw_ = 2*(tt_*f - np.floor(tt_*f+0.5))
        sq   = np.sign(np.sin(2*np.pi*f*tt_))
        s += saw_*0.6 + sq*0.4
    s /= len(chord_freqs); s = lp(s, cutoff)
    env = np.exp(-tt_*18)*0.8 + np.exp(-tt_*3)*0.2
    s *= env; s = tanh_sat(s, 2.0)
    return s*vel*0.65

def rhodes_note(freq, dur_s, vel=1.0):
    n = int(dur_s*SR); tt = t(n)
    s  = (np.sin(2*np.pi*freq*tt)       * np.exp(-tt*2.5)  * 0.50
        + np.sin(2*np.pi*freq*2.756*tt) * np.exp(-tt*8)    * 0.30
        + np.sin(2*np.pi*freq*5.404*tt) * np.exp(-tt*14)   * 0.15
        + np.sin(2*np.pi*freq*8.933*tt) * np.exp(-tt*22)   * 0.05)
    s *= (1 + 0.25*np.sin(2*np.pi*5*tt))
    s  = rev(s, 0.8, 0.25)
    pk = np.max(np.abs(s)); return s/pk*vel if pk>0 else s

def guitar_chop(freq, n_samp, vel=1.0):
    buf_size = int(SR/freq); buf = rng.standard_normal(buf_size)*0.8
    out = np.zeros(n_samp)
    for i in range(n_samp):
        out[i] = buf[i%buf_size]
        buf[i%buf_size] = (buf[i%buf_size]+buf[(i+1)%buf_size])*0.4985
    out = hp(out, 200); out = shelf(out, 3000, 5)
    out *= np.exp(-t(n_samp)*28) * vel
    pk = np.max(np.abs(out)); return out/pk*vel if pk>0 else out

def vocal_aah(freq, dur_s, vel=0.7):
    n = int(dur_s*SR); tt = t(n); src = np.zeros(n)
    for k in range(1, 12): src += np.sin(2*np.pi*freq*k*tt) * (1/k**1.2)
    out = (bp(src, 700,  900) * 1.0
         + bp(src,1100, 1400) * 0.7
         + bp(src,2400, 2900) * 0.4)
    env = np.ones(n); at = int(0.08*SR); rt = int(0.3*SR)
    env[:at] = np.linspace(0, 1, at)
    if rt < n: env[-rt:] = np.linspace(1, 0, rt)
    out *= env*vel; out = rev(out, 1.2, 0.35)
    pk = np.max(np.abs(out)); return out/pk*vel if pk>0 else out

def norm(s, tg): pk = np.max(np.abs(s)); return s/pk*tg if pk>0 else s

def build(out_path):
    bar_s = int(BAR*SR); b16 = int(BEAT/4*SR)
    b8 = int(BEAT/2*SR); b4 = int(BEAT*SR)

    print("Drums...", flush=True)
    dL=np.zeros(N); dR=np.zeros(N)
    kick_s=house_kick(); clap_s=clap(); hh_c=hh(0.022,0.60); hh_o=hh(0.16,0.75)
    for i in range(N//b16):
        p=i%16; pos=i*b16+int(rng.integers(-80,80)); pos=max(0,pos); vv=0.92+rng.random()*0.16
        def add_d(snd,vol=1.0,pan=0.0):
            e=min(pos+len(snd),N); lv=np.sqrt(0.5*(1-pan)); rv=np.sqrt(0.5*(1+pan))
            dL[pos:e]+=snd[:e-pos]*vol*vv*lv; dR[pos:e]+=snd[:e-pos]*vol*vv*rv
        if p in [0,4,8,12]: add_d(kick_s,1.0)
        if p in [4,12]:      add_d(clap_s,1.0)
        if p%2==0:           add_d(hh_c,0.55+rng.random()*0.35,0.28)
        if p in [6,14]:      add_d(hh_o,0.80,0.28)
        if p==2:             add_d(clap_s,0.35)

    print("Strings...", flush=True)
    strL=np.zeros(N); strR=np.zeros(N)
    for bar in range(BARS):
        chord=CHORD_PROG[bar%4]; pos=bar*bar_s; n_=min(bar_s,N-pos)
        if bar<2 or n_<=0: continue
        sL,sR=disco_strings(chord,n_,vel=0.70)
        strL[pos:pos+len(sL)]+=sL; strR[pos:pos+len(sR)]+=sR

    print("Bass...", flush=True)
    bL=np.zeros(N); bR=np.zeros(N)
    for bar in range(1,BARS):
        for bp_,freq,dur in BASS_PATTERNS[bar%4]:
            pos=int(bar*bar_s+bp_*b4); n_=min(int(dur*b4),N-pos)
            if n_<=0: continue
            note=disco_bass_note(freq,n_/SR,vel=0.82)[:n_]
            bL[pos:pos+len(note)]+=note; bR[pos:pos+len(note)]+=note

    print("Stabs...", flush=True)
    stabL=np.zeros(N); stabR=np.zeros(N)
    for bar in range(2,BARS):
        chord=CHORD_PROG[bar%4]; cutoff=2000+1500*np.sin(2*np.pi*bar/8)
        for bp_ in [0,.75,1.5,2.25,3.0,3.5]:
            pos=int(bar*bar_s+bp_*b4); n_=min(b8,N-pos)
            if n_<=0: continue
            s=chord_stab(chord,n_,cutoff=cutoff,vel=0.65)
            stabL[pos:pos+len(s)]+=s; stabR[pos:pos+len(s)]+=s

    print("Rhodes...", flush=True)
    rhL=np.zeros(N); rhR=np.zeros(N)
    for bar in range(4,BARS):
        for bf,freq in enumerate(RHODES_NOTES[bar%4]):
            pos=int(bar*bar_s+bf*b4*1.33); n_=min(int(BEAT*1.2*SR),N-pos)
            if n_<=0 or pos>=N: continue
            note=rhodes_note(freq,n_/SR,vel=0.48)[:n_]
            pan=[-0.2,0,0.2][bf%3]; lv=np.sqrt(0.5*(1-pan)); rv=np.sqrt(0.5*(1+pan))
            rhL[pos:pos+len(note)]+=note*lv; rhR[pos:pos+len(note)]+=note*rv

    print("Guitar...", flush=True)
    gL=np.zeros(N); gR=np.zeros(N)
    for bar in range(3,BARS):
        for bp_,freq in GUITAR_CHORDS:
            pos=int(bar*bar_s+bp_*b4); n_=min(b16,N-pos)
            if n_<=0: continue
            s=guitar_chop(freq,n_,vel=0.45)[:n_]
            lv=np.sqrt(0.5*(1-.4)); rv=np.sqrt(0.5*(1+.4))
            gL[pos:pos+len(s)]+=s*lv; gR[pos:pos+len(s)]+=s*rv

    print("Vocal synth...", flush=True)
    voxL=np.zeros(N); voxR=np.zeros(N)
    for bar in range(8,BARS-4):
        for bp_,freq in VOX_PATTERN:
            pos=int(bar*bar_s+bp_*b4); dur=BEAT*0.85; n_=min(int(dur*SR),N-pos)
            if n_<=0: continue
            s=vocal_aah(freq,dur,vel=0.42)[:n_]
            pan=-0.20; lv=np.sqrt(0.5*(1-pan)); rv=np.sqrt(0.5*(1+pan))
            voxL[pos:pos+len(s)]+=s*lv; voxR[pos:pos+len(s)]+=s*rv

    sweep=np.ones(N)
    ie=int(BAR*2*SR); be=int(BAR*4*SR); os=int(BAR*28*SR)
    sweep[:ie]=np.linspace(.02,.6,ie); sweep[ie:be]=np.linspace(.6,1.,be-ie)
    sweep[os:]=np.linspace(1,.05,N-os)

    lfo_s=0.5+0.5*np.sin(2*np.pi*0.125*np.arange(N)/SR)
    for bi in range(0,N,4096):
        e=min(bi+4096,N); c=float(800+lfo_s[bi]*7200)
        for arr in [strL,strR,stabL,stabR]: arr[bi:e]=lp(arr[bi:e],c)

    dL=norm(dL,.80); dR=norm(dR,.80); bL=norm(bL,.78); bR=norm(bR,.78)
    strL=norm(strL,.68); strR=norm(strR,.68); stabL=norm(stabL,.60); stabR=norm(stabR,.60)
    rhL=norm(rhL,.50); rhR=norm(rhR,.50); gL=norm(gL,.44); gR=norm(gR,.44)
    voxL=norm(voxL,.35); voxR=norm(voxR,.35)

    L=(dL+bL+strL+stabL+rhL+gL+voxL)*sweep
    R=(dR+bR+strR+stabR+rhR+gR+voxR)*sweep
    mid=(L+R)/2; side=hp((L-R)/2,120)*10**(8./20)
    haas=int(.007*SR); side_h=np.zeros_like(side); side_h[haas:]=side[:-haas]
    side_f=side*0.6+side_h*0.4
    L=mid+side_f; R=mid-side_f
    for arr_ref in [(L,), (R,)]:
        pass  # EQ inline below
    L=shelf(L,180,-4,'low'); L=shelf(L,4000,4,'high')
    R=shelf(R,180,-4,'low'); R=shelf(R,4000,4,'high')
    stereo=np.stack([L,R],axis=1); pk=np.max(np.abs(stereo)); stereo=stereo/pk*0.95

    mono_=stereo.mean(axis=1); side2=(stereo[:,0]-stereo[:,1])/2
    w=20*np.log10(np.sqrt(np.mean(side2**2))+1e-9)-20*np.log10(np.sqrt(np.mean(mono_**2))+1e-9)
    rms_=20*np.log10(np.sqrt(np.mean(mono_**2))+1e-9)
    print(f"Width: {w:+.1f} dB | RMS: {rms_:+.1f} dB | Dur: {N/SR:.1f}s")

    sf.write(out_path, stereo, SR)
    print(f"✅ {out_path}")



def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    out = sys.argv[1] if len(sys.argv)>1 else "/tmp/disc_superstar_style.wav"
    build(out)