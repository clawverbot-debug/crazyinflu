base=open("gen_song.py").read()
a=base.index('LYRICS = """'); c=base.index('NEG = ')
LY='''LYRICS = """[Intro]
Prime Ads! (Prime Ads!)
Meta media buyers, this one's for you!

[Chorus]
Prime Ads, the best agency accounts
Meta ad accounts to scale your Q4
Built to stay live, built to stay live
Prime Ads, built to stay live

[Verse]
For Meta media buyers only
Bigger budgets, scale it up
Q4 is coming, are you ready?
Contact us now, Prime Ads!

[Chorus]
Prime Ads, the best agency accounts
Meta ad accounts to scale your Q4
Built to stay live, built to stay live
Prime Ads, built to stay live

[Outro]
Contact us now! Prime Ads!"""
'''
for tag,bpm,feel in [("A",118,"bouncy party dance groove"),("B",84,"slow heavy half-time bounce")]:
    st=('STYLE = ("Catchy dance anthem, %d bpm, %s, punchy kick on every beat, claps, deep bass, shakers, "\n'
        '         "energetic male group chant vocals in English starting on the first beat, PRIME ADS shouted clearly as two words, "\n'
        '         "advert jingle energy, viral dance challenge, very clear diction")\n') % (bpm, feel)
    s=base[:a]+LY+st+base[c:]
    s=s.replace("Knock Knock (Who's There)","Built To Stay Live (%s)" % tag)
    s=s.replace("knock_knock_full_","promo%s_full_" % tag)
    open("gen_promo_%s.py" % tag,"w").write(s)
print("ok")
