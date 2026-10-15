import runpy,sys,torch,atexit,time
t=time.time()
atexit.register(lambda: print("TOTAL s",round(time.time()-t,1),"PEAK VRAM GB",round(torch.cuda.max_memory_allocated()/1e9,2)))
sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name="__main__")
