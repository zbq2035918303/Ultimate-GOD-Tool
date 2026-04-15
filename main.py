import os, shutil, random, subprocess, threading, queue, time
import customtkinter as ctk
from tkinter import filedialog, messagebox

ctk.set_appearance_mode("dark")

# ========= AI =========
def ai_analyze(path, size):
    p = path.lower()
    if "windows" in p or "program files" in p:
        return "❌ 禁止迁移"
    if size > 2*1024**3 or "game" in p:
        return "✅ 推荐迁移"
    return "⚠️ 可迁移"

# ========= 工具 =========
def fast_size(path, limit=800):
    total=0; count=0
    try:
        for root,_,files in os.walk(path):
            for f in files:
                try:
                    total+=os.path.getsize(os.path.join(root,f))
                    count+=1
                    if count>limit:
                        return total
                except: pass
    except: pass
    return total

def build_tree(path, depth=2):
    res=[]
    try:
        for e in os.scandir(path):
            size=fast_size(e.path)
            children=build_tree(e.path,depth-1) if e.is_dir() and depth>0 else []
            res.append({"path":e.path,"size":size,"children":children})
    except: pass
    return res

def get_color(p):
    return "#%02x%02x%02x"%(random.randint(80,200),random.randint(80,200),random.randint(80,200))

# ========= 安全迁移 =========
def safe_move_with_link(src, dst, log=None):
    new = os.path.join(dst, os.path.basename(src))
    try:
        if not os.path.exists(src): return False
        if os.path.exists(new): return False
        if "windows" in src.lower() or "program files" in src.lower():
            return False

        shutil.move(src, new)
        subprocess.run(f'mklink /J "{src}" "{new}"', shell=True)

        if not os.path.exists(src):
            raise Exception("link fail")

        if log: log(f"✅ {src} → {new}\n")
        return True
    except:
        try:
            if os.path.exists(new):
                shutil.move(new, src)
        except: pass
        if log: log(f"❌ 失败: {src}\n")
        return False

# ========= Treemap =========
class Treemap:
    def __init__(self, root, data):
        self.root=root
        self.data=data
        self.history=[]

        self.canvas=ctk.CTkCanvas(root,bg="#111")
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<Configure>", self.draw)

        self.tooltip=ctk.CTkLabel(root,text="",fg_color="#222")
        self.tooltip.place_forget()

    def layout(self,data,x,y,w,h,vertical):
        total=sum(d["size"] for d in data) or 1
        rects=[]; offset=0
        for d in data:
            ratio=d["size"]/total
            if vertical:
                ww=w*ratio
                rects.append((x+offset,y,ww,h,d))
                offset+=ww
            else:
                hh=h*ratio
                rects.append((x,y+offset,w,hh,d))
                offset+=hh
        return rects

    def draw(self,event=None):
        self.canvas.delete("all")
        w=self.canvas.winfo_width()
        h=self.canvas.winfo_height()
        if w<10:return
        self.draw_recursive(self.data,0,0,w,h,True)

    def draw_recursive(self,data,x,y,w,h,vertical):
        rects=self.layout(data,x,y,w,h,vertical)
        for rx,ry,rw,rh,d in rects:
            if rw<2 or rh<2: continue

            rect=self.canvas.create_rectangle(rx,ry,rx+rw,ry+rh,
                fill=get_color(d["path"]),outline="#222")

            self.canvas.tag_bind(rect,"<Enter>",lambda e,dd=d:self.show_tip(e,dd))
            self.canvas.tag_bind(rect,"<Motion>",lambda e:self.move_tip(e))
            self.canvas.tag_bind(rect,"<Leave>",lambda e:self.hide_tip())
            self.canvas.tag_bind(rect,"<Button-1>",lambda e,dd=d:self.zoom(dd))
            self.canvas.tag_bind(rect,"<Button-3>",lambda e,dd=d:self.menu(e,dd))

            if d["children"]:
                self.draw_recursive(d["children"],rx,ry,rw,rh,not vertical)

    def zoom(self,d):
        if d["children"]:
            self.history.append(self.data)
            self.data=d["children"]
            self.draw()

    def back(self):
        if self.history:
            self.data=self.history.pop()
            self.draw()

    def show_tip(self,e,d):
        self.tooltip.configure(text=f"{d['path']}\n{d['size']//1024//1024}MB")
        self.tooltip.place(x=e.x+15,y=e.y+15)

    def move_tip(self,e):
        self.tooltip.place(x=e.x+15,y=e.y+15)

    def hide_tip(self):
        self.tooltip.place_forget()

    def menu(self,e,d):
        m=ctk.CTkToplevel(self.root)
        m.geometry(f"160x140+{e.x_root}+{e.y_root}")
        ctk.CTkButton(m,text="打开",command=lambda:os.startfile(d["path"])).pack(fill="x")
        ctk.CTkButton(m,text="删除",command=lambda:shutil.rmtree(d["path"],ignore_errors=True)).pack(fill="x")
        ctk.CTkButton(m,text="迁移",command=lambda:self.move(d)).pack(fill="x")

    def move(self,d):
        dst=filedialog.askdirectory()
        if dst:
            safe_move_with_link(d["path"],dst)

# ========= 主程序 =========
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("1200x750")
        self.title("Ultimate GOD Tool FINAL")

        self.log_queue=queue.Queue()
        self.progress_var=ctk.DoubleVar(value=0)

        left=ctk.CTkFrame(self,width=200)
        left.pack(side="left",fill="y")

        ctk.CTkButton(left,text="磁盘分析",command=self.disk).pack(pady=10)
        ctk.CTkButton(left,text="清理",command=self.clean).pack(pady=10)
        ctk.CTkButton(left,text="C盘变大",command=self.c_boost).pack(pady=10)
        ctk.CTkButton(left,text="扫描",command=self.scan).pack(pady=10)
        ctk.CTkButton(left,text="迁移",command=self.migrate_ui).pack(pady=10)

        self.box=ctk.CTkTextbox(self)
        self.box.pack(fill="both",expand=True)

        self.progress=ctk.CTkProgressBar(self,variable=self.progress_var)
        self.progress.pack(fill="x")

        self.data=[]

    def log(self,msg):
        self.box.insert("end",msg)
        self.box.see("end")

    # ===== 磁盘 =====
    def disk(self):
        p=filedialog.askdirectory()
        if not p:return
        data=build_tree(p)
        win=ctk.CTkToplevel(self)
        win.geometry("1000x600")
        tm=Treemap(win,data)
        ctk.CTkButton(win,text="返回",command=tm.back).pack()

    # ===== 清理 =====
    def clean(self):
        win=ctk.CTkToplevel(self)
        win.geometry("600x500")

        frame=ctk.CTkScrollableFrame(win)
        frame.pack(fill="both",expand=True)

        self.clean_items=[]

        paths=[
            ("系统临时",os.environ.get("TEMP")),
            ("Windows缓存","C:\\Windows\\Temp"),
            ("用户缓存",os.path.expanduser("~\\AppData\\Local\\Temp"))
        ]

        for name,path in paths:
            if not path or not os.path.exists(path):continue
            size=fast_size(path)
            var=ctk.BooleanVar(value=True)

            cb=ctk.CTkCheckBox(frame,text=f"{name} | {size//1024//1024}MB",variable=var)
            cb.pack(anchor="w")

            self.clean_items.append((path,var))

        self.clean_progress=ctk.CTkProgressBar(win)
        self.clean_progress.pack(fill="x")

        ctk.CTkButton(win,text="开始清理",command=self.start_clean).pack()

    def start_clean(self):
        items=[x for x in self.clean_items if x[1].get()]
        t=threading.Thread(target=self.clean_worker,args=(items,))
        t.start()
        self.after(100,self.update_ui)

    def clean_worker(self,items):
        total=len(items)
        done=0
        for path,var in items:
            self.log_queue.put(f"清理: {path}\n")
            try:
                for root,dirs,files in os.walk(path):
                    for f in files:
                        try: os.remove(os.path.join(root,f))
                        except: pass
                    for d in dirs:
                        try: shutil.rmtree(os.path.join(root,d),ignore_errors=True)
                        except: pass
                self.log_queue.put("完成\n")
            except:
                self.log_queue.put("失败\n")

            done+=1
            self.log_queue.put(("CLEAN",done/total))

    # ===== C盘优化 =====
    def c_boost(self):
        win=ctk.CTkToplevel(self)
        win.geometry("500x400")

        frame=ctk.CTkFrame(win)
        frame.pack(fill="both",expand=True,padx=10,pady=10)

        self.boost_options=[]

        opts=[
            ("关闭休眠（释放空间）","hibernate"),
            ("清空回收站","recycle"),
            ("清理系统缓存","cache"),
            ("清理更新缓存","update")
        ]

        for name,key in opts:
            var=ctk.BooleanVar(value=True)
            cb=ctk.CTkCheckBox(frame,text=name,variable=var)
            cb.pack(anchor="w")
            self.boost_options.append((key,var))

        self.boost_progress=ctk.CTkProgressBar(win)
        self.boost_progress.pack(fill="x")

        ctk.CTkButton(win,text="开始优化",command=self.start_boost).pack()

    def start_boost(self):
        items=[x for x in self.boost_options if x[1].get()]
        t=threading.Thread(target=self.boost_worker,args=(items,))
        t.start()
        self.after(100,self.update_ui)

    def boost_worker(self,items):
        total=len(items)
        done=0
        for key,var in items:
            try:
                if key=="hibernate":
                    subprocess.run("powercfg -h off",shell=True)
                elif key=="recycle":
                    subprocess.run("rd /s /q C:\\$Recycle.Bin",shell=True)
                elif key=="cache":
                    shutil.rmtree("C:\\Windows\\Temp",ignore_errors=True)
                elif key=="update":
                    shutil.rmtree("C:\\Windows\\SoftwareDistribution\\Download",ignore_errors=True)

                self.log_queue.put("优化完成\n")
            except:
                self.log_queue.put("失败\n")

            done+=1
            self.log_queue.put(("BOOST",done/total))

    # ===== 扫描 =====
    def scan(self):
        p=filedialog.askdirectory()
        if not p:return
        self.data=[]
        self.box.delete("1.0","end")

        for e in os.scandir(p):
            size=fast_size(e.path)
            s=ai_analyze(e.path,size)
            self.data.append((e.path,s))
            self.log(f"{e.path} | {s}\n")

    # ===== 迁移 =====
    def migrate_ui(self):
        win=ctk.CTkToplevel(self)
        win.geometry("800x600")

        frame=ctk.CTkScrollableFrame(win)
        frame.pack(fill="both",expand=True)

        self.check_vars=[]

        for p,s in self.data:
            var=ctk.BooleanVar(value=False)
            color="#00ff99" if "推荐" in s else "#ffffff"

            cb=ctk.CTkCheckBox(frame,text=f"{p} | {s}",variable=var,text_color=color)
            cb.pack(anchor="w")

            self.check_vars.append((p,var,s))

        ctk.CTkButton(win,text="勾选推荐项",command=self.select_recommended).pack()

        self.target=ctk.StringVar()
        ctk.CTkEntry(win,textvariable=self.target).pack(fill="x")

        ctk.CTkButton(win,text="选择路径",command=self.select).pack()
        ctk.CTkButton(win,text="开始迁移",command=self.start_move).pack()

    def select_recommended(self):
        for p,var,s in self.check_vars:
            if "推荐" in s:
                var.set(True)

    def select(self):
        p=filedialog.askdirectory()
        if p:self.target.set(p)

    def start_move(self):
        base=self.target.get()
        items=[x for x in self.check_vars if x[1].get()]
        t=threading.Thread(target=self.worker,args=(items,base))
        t.start()
        self.after(100,self.update_ui)

    def worker(self,items,base):
        total=len(items)
        done=0
        for p,var,s in items:
            self.log_queue.put(f"迁移: {p}\n")
            ok=safe_move_with_link(p,base)
            self.log_queue.put("成功\n" if ok else "失败\n")
            done+=1
            self.log_queue.put(("P",done/total))
        self.log_queue.put("完成\n")

    # ===== UI更新 =====
    def update_ui(self):
        while not self.log_queue.empty():
            m=self.log_queue.get()

            if isinstance(m,tuple):
                if m[0]=="P":
                    self.progress_var.set(m[1])
                elif m[0]=="CLEAN":
                    try:self.clean_progress.set(m[1])
                    except:pass
                elif m[0]=="BOOST":
                    try:self.boost_progress.set(m[1])
                    except:pass
            else:
                self.log(m)

        self.after(100,self.update_ui)

if __name__=="__main__":
    App().mainloop()