import bpy, sys
paths = sys.argv[sys.argv.index('--')+1:]
pts = {"wall_shade_top":(700,100),"wall_shade_mid":(600,250),"wall_sun":(540,470),"wall_sun2":(800,640),"wall_lowright":(900,780),
 "floor_far":(400,780),"floor_mid":(600,880),"floor_near":(850,960),"skirting":(600,806),"sofa_arm":(140,730),"sofa_front":(130,880),
 "ceiling":(100,15),"trim":(145,300),"corner_wall":(215,400)}
for p in paths:
    img = bpy.data.images.load(p)
    w,h = img.size
    px = list(img.pixels)
    out=[]
    for k,(x,y) in pts.items():
        X=int(x/1000*w); Y=int(y/1000*h); r=max(2,int(6*w/1000))
        acc=[0,0,0];n=0
        for dy in range(-r,r+1):
            for dx in range(-r,r+1):
                xx=min(max(X+dx,0),w-1); yy=min(max(h-1-(Y+dy),0),h-1)
                i=(yy*w+xx)*4
                for c in range(3): acc[c]+=px[i+c]
                n+=1
        out.append("%s=%s"%(k,tuple(round(255*(a/n)**(1/2.2)) for a in acc)))
    import os; print("PROBE", os.path.basename(p), " ".join(out))
