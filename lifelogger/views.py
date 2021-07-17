from django.shortcuts import render
from django.urls import reverse
from django.http import  HttpResponse, HttpResponseRedirect, Http404, JsonResponse
from django.contrib import messages

from django.utils.safestring import mark_safe

from lifelogger.models import User_info
from lifelogger.models import SaveFile

import os
import sqlite3
import pandas as pd 
import numpy as np
import datetime
import xlsxwriter
import json

import sys
ABSPATH = os.path.abspath("../../../MoodWork/")
sys.path.append(os.path.join(ABSPATH,"user_study/Music_recommendation/HappyRec/"))
from recommender import Recommender

from django.views.decorators.csrf import csrf_exempt

# Create your views here.

user_info = User_info()

def choose_file_load(request):
    # 在首页上选择点击之后进入哪个页面：上传手环数据或上传标注表格
    user_name = request.POST['user_name']
    if request.POST.get('wrist'):
        return HttpResponseRedirect(reverse("lifelogger:uploadfile",args=[user_name]))
    if request.POST.get('table'):
        return HttpResponseRedirect(reverse("lifelogger:uploadtable",args=[user_name]))
    if request.POST.get('mood'):
        return HttpResponseRedirect(reverse("lifelogger:labelmood",args=[user_name]))
    if request.POST.get('data'):
        return HttpResponseRedirect(reverse("lifelogger:datatest",args=[user_name]))
    if request.POST.get('music'):
        return HttpResponseRedirect(reverse("lifelogger:preference_start",args=[user_name]))
    if request.POST.get('music_remain'):
        return HttpResponseRedirect(reverse("lifelogger:preference_remain",args=[user_name]))


def homepage(request):
    # 首页
    if request.POST.get("register"):
        return HttpResponseRedirect(reverse("lifelogger:register"))
    if request.POST.get('user_name'):
        user_name = request.POST['user_name']
        password = request.POST['password']
        userinfo = User_info.objects.filter(name=user_name)
        if userinfo.exists():
            # 检验密码
            user = User_info.objects.get(name=user_name)
            if user.password == password:
                return choose_file_load(request)
            else:
                messages.error(request,'用户名或密码不正确！')
        else:
            messages.error(request,"用户不存在，请先注册！")

    return render(request, "lifelogger/homepage.html")

def register(request):
    print("REGISTER")
    if request.method == "POST": 
        if "register" in request.POST:
            user_name = request.POST['user_name']
            password = request.POST['password']
            password2 = request.POST['password2']
            userinfo = User_info.objects.filter(name=user_name)
            if userinfo.exists():
                print("exist")
                messages.error(request,"该用户名存在，请重选！")
            elif password != password2:
                messages.error(request,"两次密码不一致！")
            # 创建新用户
            else:
                os.mkdir(os.path.join("./lifelogger/static/",user_name))
                new_user = User_info(name=user_name,password=password)
                new_user.save()
                messages.success(request,"新建用户！")
                return HttpResponseRedirect(reverse("lifelogger:homepage"))
        if "return" in request.POST:
            return HttpResponseRedirect(reverse("lifelogger:homepage"))

    return render(request,"lifelogger/register.html")

def preference_start(request, user_name):

    if request.method == "POST" and "start" in request.POST:
        return HttpResponseRedirect(reverse("lifelogger:preference",args=[user_name]))

    return render(request,"lifelogger/preference_start.html")

def preference(request,user_name):
    # 显示20首音乐的列表，要求preference评级
    save_path = os.path.join("./lifelogger/static",user_name)
    recommender = Recommender(user_name,data_path = os.path.join(ABSPATH,"user_study/Music_recommendation/HappyRec/dataset/music"),
                                    original_datapth=os.path.join(ABSPATH,"dataset/music/Formal_1k_final/"))
    random_list = recommender.random_generate(20)
    random_list = [random_list[0]] + random_list 
    def construct_name(idx):
        return "music/"+random_list[idx][2]+"-"+random_list[idx][1]+".mp3";
    try:
        with open(os.path.join(save_path,"preference.json"),"r") as F:
            results = json.load(F)
    except:
        results = {}
    if request.method=="POST":
        if "start" in request.POST and request.POST["start"]:
            print("start")
            print(request.POST["start"])
            return render(request,"lifelogger/preference.html",{"music":random_list,"id":1,"results":results,"music_name":construct_name(1)})
        print('start handling')
        console = request.POST["audio_time"]
        with open(os.path.join(save_path,"audio_time.txt"),"a") as F:
            F.write(console)
        page_time = request.POST["page_time"]
        with open(os.path.join(save_path,"page_time.txt"),"a") as F:
            F.write(page_time)
        print("file saved")
        this_id = int(request.POST["this_id"])
        this_rating = 0
        this_coordinates = "0,0"
        if "coordinate_result" in request.POST and len(request.POST["coordinate_result"].split(","))==2: 
            this_coordinates = request.POST["coordinate_result"]
        if "rating_result" in request.POST and len(request.POST["rating_result"])>0:
            this_rating = int(request.POST["rating_result"])
        results[this_id] = [random_list[this_id][0],this_rating,this_coordinates, random_list[this_id][3]]
        print('data update')
        if this_rating == 0 or this_coordinates == "0,0":
            with open(os.path.join(save_path,"preference.json"),"w") as F:
                json.dump(results,F)
            messages.error(request,"请完成填写后再翻页！")
            return render(request, "lifelogger/preference.html",{"music":random_list,"id":this_id,"results":results,"music_name":construct_name(this_id)})        
        with open(os.path.join(save_path,"preference.json"),"w") as F:
            json.dump(results,F)
        print('json saved')
        if "submit" in request.POST and request.POST["submit"]:
            # update数据: 
            result_list = []
            for result in results.values():
                x,y = result[2].strip().split(",")
                x = (float(x)-0.287)/(0.717-0.287)*8-4
                y = -(float(y)-0.086)/(0.914-0.086)*8+4
                mood = "%.3f,%.3f"%(x,y)
                info = [result[0], 1, result[1], "0,0", mood, result[3]]
                result_list.append(info)
            recommender.data_update(result_list,stage="lab")
            recommender.save_file()
            return HttpResponseRedirect(reverse("lifelogger:thanks"))
        else:
            next_id = 0
            if this_id % 5 == 0:
                messages.success(request,"您已经听了%d首歌，联系主试，休息一下吧！"%(this_id))
            if "last" in request.POST and request.POST["last"]:
                next_id = this_id-1
            elif "next" in request.POST and request.POST["next"]:
                next_id = this_id+1
            return render(request, "lifelogger/preference.html",{"music":random_list,"id":next_id,"results":results,"music_name":construct_name(next_id)})        
    return render(request,"lifelogger/preference.html",{"music":random_list,"id":0, "results":results,"music_name":construct_name(0)})    

def preference_remain(request,user_name):
    # 显示20首音乐的列表，要求preference评级
    save_path = os.path.join("./lifelogger/static",user_name)
    recommender = Recommender(user_name,data_path = os.path.join(ABSPATH,"user_study/Music_recommendation/HappyRec/dataset/music"),
                                    original_datapth=os.path.join(ABSPATH,"dataset/music/Formal_1k_final/"))
    random_list = recommender.random_remain(20)
    def construct_name(idx):
        return "music/"+random_list[idx][2]+"-"+random_list[idx][1]+".mp3";
    try:
        with open(os.path.join(save_path,"preference_remain.json"),"r") as F:
            results = json.load(F)
    except:
        results = {}
    if request.method=="POST":
        if "start" in request.POST and request.POST["start"]:
            print("start")
            print(request.POST["start"])
            return render(request,"lifelogger/preference.html",{"music":random_list,"id":1,"results":results,"music_name":construct_name(1)})
        print('start handling')
        console = request.POST["audio_time"]
        with open(os.path.join(save_path,"audio_time_remain.txt"),"a") as F:
            F.write(console)
        page_time = request.POST["page_time"]
        with open(os.path.join(save_path,"page_time_remain.txt"),"a") as F:
            F.write(page_time)
        print("file saved")
        this_id = int(request.POST["this_id"])
        this_rating = 0
        this_coordinates = "0,0"
        if "coordinate_result" in request.POST and len(request.POST["coordinate_result"].split(","))==2: 
            this_coordinates = request.POST["coordinate_result"]
        if "rating_result" in request.POST and len(request.POST["rating_result"])>0:
            this_rating = int(request.POST["rating_result"])
        results[this_id] = [random_list[this_id][0],this_rating,this_coordinates, random_list[this_id][3]]
        print('data update')
        if this_rating == 0 or this_coordinates == "0,0":
            with open(os.path.join(save_path,"preference_remain.json"),"w") as F:
                json.dump(results,F)
            messages.error(request,"请完成填写后再翻页！")
            return render(request, "lifelogger/preference.html",{"music":random_list,"id":this_id,"results":results,"music_name":construct_name(this_id)})        
        with open(os.path.join(save_path,"preference_remain.json"),"w") as F:
            json.dump(results,F)
        print('json saved')
        if "submit" in request.POST and request.POST["submit"]:
            # update数据: 
            result_list = []
            for result in results.values():
                x,y = result[2].strip().split(",")
                x = (float(x)-0.287)/(0.717-0.287)*8-4
                y = -(float(y)-0.086)/(0.914-0.086)*8+4
                mood = "%.3f,%.3f"%(x,y)
                info = [result[0], 1, result[1], "0,0", mood, result[3]]
                result_list.append(info)
            recommender.data_update(result_list,stage="lab2")
            recommender.save_file()
            return HttpResponseRedirect(reverse("lifelogger:thanks"))
        else:
            next_id = 0
            if "last" in request.POST and request.POST["last"]:
                next_id = this_id-1
            elif "next" in request.POST and request.POST["next"]:
                next_id = this_id+1
            return render(request, "lifelogger/preference.html",{"music":random_list,"id":next_id,"results":results,"music_name":construct_name(next_id)})        
    return render(request,"lifelogger/preference.html",{"music":random_list,"id":0, "results":results,"music_name":construct_name(0)})    

def train_model(request):
    if request.method == "POST":
        user_name = request.POST["user_name"]
        save_path = os.path.join("./lifelogger/static",user_name)
        if os.path.isfile(os.path.join(save_path,"preference.json")):
            recommender = Recommender(user_name,data_path = os.path.join(ABSPATH,"user_study/Music_recommendation/HappyRec/dataset/music"),original_datapth=os.path.join(ABSPATH,"dataset/music/Formal_1k_final/"))
            recommender.model_training()    
        else:
            error = "User %s did not collect preference!"
            return HttpResponse(error)
    return render(request,"lifelogger/train.html")

@csrf_exempt
def recommendation(request,user_name):
    print("user name:",user_name)
    if "__" in user_name:
        user_name,pmood = user_name.strip().split("__")
    else:
        pmood = '0,0'
    save_path = os.path.join("./lifelogger/static",user_name)
    if datetime.datetime.fromtimestamp(1618099200).hour == 8:
        Now = datetime.datetime.now()
    else:
        Now = datetime.datetime.now() + datetime.timedelta(hours=8)
    recommender = Recommender(user_name,data_path = os.path.join(ABSPATH,"user_study/Music_recommendation/HappyRec/dataset/music"),original_datapth=os.path.join(ABSPATH,"dataset/music/Formal_1k_final/"))
    if request.method == "POST":
        with open(os.path.join(save_path,"recommendation_time.txt"),"a") as F:
            F.write("return\t"+str(Now)+"\n")
        music_json = json.loads(request.POST["music"])
        print("MUSIC_POST")
        print(music_json)
        music_list = []
        f_name = ["mid","click","preference","mood_before","mood_after","valence"]
        for music in music_json:
            music_dict = eval(music_json[music])
            print(music_dict)
            music_info = []
            for f in f_name:
                if f in ["click","preference"]:
                    music_info.append(int(music_dict[f]))
                elif f == "valence":
                    music_info.append(float(music_dict[f]))
                else:
                    music_info.append(music_dict[f])
            music_list.append(music_info)
        print(music_list)
        recommender.data_update(music_list,stage="field")
        recommender.save_file()
        return HttpResponse("Successfully update!")
    # 进行音乐推荐
    elif request.method=="GET":
        with open(os.path.join(save_path,"recommendation_time.txt"),"a") as F:
            F.write("recommend\t"+str(Now)+"\n")
        results = recommender.recommend(pmood)
        print(results)
        dict_results = {}
        f_name = ["mid","music","singer","valence","url"]
        for iid, item in enumerate(results):
            dict_results[iid] = {}
            for i,feature in enumerate(item):
                dict_results[iid][f_name[i]] = feature
        return JsonResponse(dict_results)
    # return render(request,"lifelogger/recommendation.html"))


def datatest(request,user_name):
    if request.method == "POST":
        obj_wrist = request.FILES.get("upload_wrist")
        obj_lifelog = request.FILES.get("upload_lifelog")
        if obj_wrist == None or obj_lifelog==None:
            messages.error(request,"请上传文件！")
            return render(request,"lifelogger/datatset.html")
        save_path = os.path.join("./lifelogger/static",user_name,str(datetime.datetime.now().date()))
        os.makedirs(save_path,exist_ok=True)
        with open(os.path.join(save_path,obj_wrist.name),"wb") as File:
            for chunk in obj_wrist.chunks():
                File.write(chunk)
        with open(os.path.join(save_path,obj_lifelog.name),"wb") as File:
            for chunk in obj_lifelog.chunks():
                File.write(chunk)
        return HttpResponseRedirect(reverse("lifelogger:dataverify",args=[user_name,obj_wrist.name,obj_lifelog.name]))
    return render(request,"lifelogger/datatest.html")

def dataverify(request,user_name,wrist_filename,lifelog_filename):
    sf = SaveFile(user_name,os.path.join("./lifelogger/static",user_name,
                    str(datetime.datetime.now().date())),wrist_filename,lifelog_filename)
    if request.method == "POST":
        delete_list = []
        for act in ['wrist','mood','gps','diet','music','act']:
            if 'data_'+act not in request.POST:
                delete_list.append(act)
        sf.delete(delete_list)
        file = sf.calculate_payment()
        return HttpResponseRedirect(reverse("lifelogger:verifydone",args=[user_name,file]))
    results = sf.prossessing()
    print(results)
    for key in results:
        results[key] = mark_safe(results[key].replace("\n","<br>"))
    if "error" in results:
        results["error_msg"] = 1
    else:
        results["error_msg"] = 0
    return render(request,"lifelogger/dataverify.html",results)

def verifydone(request,user_name,file):
    if request.method == "POST":
        print("POST")
        return HttpResponseRedirect(reverse("lifelogger:homepage"))
    file_name = os.path.join(user_name,str(datetime.datetime.now().date()),file)
    return render(request,"lifelogger/verifydone.html",{"file":file_name})

def uploadfile(request,user_name):
    # 提交手环数据
    if request.method == "POST":
        obj = request.FILES.get("upload")
        if obj == None:
            messages.error(request,"请上传文件！")
            return render(request,"lifelogger/uploadfile.html")
        set_day = request.POST["date_selector"]
        year, month, day = [int(x) for x in set_day.split("-")]
        set_day = datetime.date(year,month,day)
        with open(os.path.join("./lifelogger/static",user_name,obj.name),"wb") as File:
            for chunk in obj.chunks():
                File.write(chunk)
                # 进行segment
                segment_file =  get_segmentation(os.path.join("./lifelogger/static",user_name,obj.name),set_day=set_day)
                if segment_file == "Not valid data":
                    messages.error(request,"请上传Gadgetbridge导出的bin文件！")
                    return render(request,"lifelogger/uploadfile.html")
                if segment_file == "No Data Today":
                    messages.error(request,"上传文件中不包含待标注日期的数据！")
                    return render(request,"lifelogger/uploadfile.html")
                if len(segment_file):
                    messages.success(request,"上传成功！")
                    return HttpResponseRedirect(reverse("lifelogger:downloadfile",args=[user_name,segment_file]))
                else:
                    messages.error(request,"出错，请重新上传！")
    return render(request,"lifelogger/uploadfile.html")

def downloadfile(request, user_name,segment_file):
    # 下载segment后的文件
    if request.POST.get("submit"):
        return HttpResponseRedirect(reverse("lifelogger:uploadtable",args=[user_name]))
    else:
        # 展示图片 & 文件下载
        content = {}
        content["Thayer_mood"] = "thayer_label3.png"
        content["download_file"] = user_name + "/" + segment_file
        return render(request, 'lifelogger/downloadfile.html', content)


def download(request,user_name, segment_file):
    # 弃用
    with open(os.path.join("./lifelogger/static",user_name,segment_file),'rb') as f:
        c = f.read()
        return HttpResponse(c)

def uploadtable(request, user_name):
    # 上传标注好的表格
    if request.method == "POST":
        obj = request.FILES.get("upload")
        file_name = obj.name
        if file_name.split(".")[-1] not in ["csv","xlsx","xls"]:
            messages.error(request,"文件格式错误！")
            return render(request,"lifelogger/uploadtable.html")
        file_name = file_name.split(".")
        file_name[-2] += "_new"
        file_name = ".".join(file_name)
        with open(os.path.join("./lifelogger/static",user_name,file_name),"wb") as File:
            for chunk in obj.chunks():
                File.write(chunk)
            messages.success(request,"上传成功！")
            return HttpResponseRedirect(reverse("lifelogger:thanks"))
    return render(request,"lifelogger/uploadtable.html")

def labelmood(request, user_name):
    if request.method == "POST":
        mood_label = {}
        event_text = (request.POST["event_text_yes"])
        # try:
        if True:
            if request.POST["event_choose"] == "yes":
                mood_label["event_choose"] = 1
                mood_label["event_text"] = request.POST["event_text_yes"]
                mood_label["event_moment"] = request.POST["event_moment"]
                coordinate = request.POST["coordinate_yes"]
                mood_label["valence"], mood_label["arousal"] = [float(x) for x in coordinate.strip().split(",")]

            elif request.POST["event_choose"] == "no":
                mood_label["event_choose"] = 0
                mood_label["event_text"] = request.POST["event_text_no"]
                mood_label["event_moment"] = str(datetime.datetime.now())
                coordinate = request.POST["coordinate_no"]
                mood_label["valence"], mood_label["arousal"] = [float(x) for x in coordinate.strip().split(",")]
            else:
                messages.error(request,"请选择是否有事件发生！")
                content = {}
                content["Thayer_mood"] = "thayer_label3.png"
                return render(request,"lifelogger/labelmood.html", content)
            if datetime.datetime.fromtimestamp(1618099200).hour == 8:
                Now = datetime.datetime.now()
            else:
                Now = datetime.datetime.now() + datetime.timedelta(hours=8)
            date = str(Now.year)+"-"+str(Now.month)+"-"+str(Now.day)
            time = str(Now.hour)+"-"+str(Now.now().minute)
            with open(os.path.join("./lifelogger/static",user_name,"mood_"+date+"_"+time+".json"),"w") as F:
                json.dump(mood_label,F)
        # except:
        #     messages.error(request,"请填写完整！")
        #     content = {}
        #     content["Thayer_mood"] = "thayer_label2.png"
        #     return render(request,"lifelogger/labelmood.html", content)

        # content = {}
        # content["Thayer_mood"] = "thayer_label2.png"
        # return render(request, 'lifelogger/labelmood.html', content)
        messages.success(request,"提交成功！")
        return HttpResponseRedirect(reverse("lifelogger:homepage"))
    content = {}
    content["Thayer_mood"] = "thayer_label3.png"
    return render(request, 'lifelogger/labelmood.html', content)

def thanks(request):
    if request.method == "POST":
        print("POST")
        return HttpResponseRedirect(reverse("lifelogger:homepage"))
    return render(request,"lifelogger/thanks.html")

def step_only(step_list,Min_interval=5,Max_limit=20):
    # Steps only segmentation
    start = [0]
    sum_step = 0
    length = 0
    def Follow_steps(step,avg_step):
        if avg_step == 0:
            return step ==0
        else:
            return abs(step-avg_step) < Max_limit
    
    for i,step in enumerate(step_list):
        avg_step = sum_step / max(length,1)
        if Follow_steps(step,avg_step):
            length += 1
            sum_step += step
            continue
        else:
            new_start = True
            for j in range(i+1,i+Min_interval):
                if Follow_steps(sum(step_list[j:j+Min_interval])/Min_interval,avg_step):
                    new_start=False
                    break
            if new_start and (i-start[-1])>=Min_interval:
                start.append(i)
                sum_step = step
                length = 1
            else:
                sum_step += step
                length += 1
    # start.append(len(step_list)-1)
    return start

def get_segmentation(file_name, set_day = datetime.date.today()):
    # load file, segment
    DATA_PATH = "/".join(file_name.split("/")[:-1])
    try:
        con = sqlite3.connect(file_name)
        c = con.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        Tables = c.fetchall()
        for t in Tables:
            if t[0] == "MI_BAND_ACTIVITY_SAMPLE":
                Records = pd.read_sql("SELECT * FROM %s"%(t[0]), con=con)
                break
        if datetime.datetime.fromtimestamp(1618099200).hour == 8:
            Records["time"] = Records["TIMESTAMP"].apply(lambda x: datetime.datetime.fromtimestamp(x))
        else:
            Records["time"] = Records["TIMESTAMP"].apply(lambda x: datetime.datetime.fromtimestamp(x+8*60*60))
    except:
        return "Not valid data"

    Records["date"] = Records["time"].apply(lambda x: x.date())
    Records["hour_min"] = Records["time"].apply(lambda x: "%02d:%02d"%(x.hour,x.minute))
    Records = Records.loc[Records["date"]==set_day].copy()
    if len(Records) == 0:
        return "No Data Today"
    Min_interval = 21
    Max_limit = 3
    start = step_only(Records.STEPS.tolist(),Min_interval,Max_limit)
    start_time = Records.iloc[start]["hour_min"].tolist()
    save_file = "%d_%d_activity.xlsx"%(set_day.month,set_day.day)

    write_excel(os.path.join(DATA_PATH, save_file), start_time,"%d_%d"%(set_day.month,set_day.day))

    c.close()
    con.close()
    return save_file

def write_excel(file_path, start_time, sheet_name):
    workbook = xlsxwriter.Workbook(file_path)
    format = workbook.add_format({})
    format.set_text_wrap()
    worksheet = workbook.add_worksheet(sheet_name)
    worksheet.write('A1',"活动开始时间")
    worksheet.write('B1',"活动类型")
    worksheet.write('C1',"具体活动")
    worksheet.write('D1',"情绪类型（十二分类情绪）")
    worksheet.write('E1',"情绪正负向")
    worksheet.write("F1","情绪强烈程度（7级，0表示非常不强烈，7表示非常强烈高）")
    worksheet.write('G1',"是否独处")
    worksheet.write('H1',"在室内/室外")
    worksheet.write('I1',"备注")
    event_list = ["学习/工作","运动","上课","吃饭","通勤","娱乐","开会","睡觉","其他"]
    mood_list = ["兴奋","愉快","高兴","放松","满足","平静","无聊","沮丧","伤心","紧张","焦虑","生气"]
    valence_list = ["非常负向","比较负向","轻微负向","中性","轻微正向","比较正向","非常正向"]
    arousal_list = np.arange(7).tolist()
    for i, time in enumerate(start_time):
        worksheet.write('A%d'%(i+2),time)
    for i in range(40):
        worksheet.data_validation("B%d"%(i+2),{'validate':"list","source":event_list})
        worksheet.data_validation("D%d"%(i+2),{'validate':"list","source":mood_list})
        worksheet.data_validation("E%d"%(i+2),{'validate':"list","source":valence_list})
        worksheet.data_validation("F%d"%(i+2),{'validate':"list","source":arousal_list})
        worksheet.data_validation("G%d"%(i+2),{'validate':"list","source":["是","否"]})
        worksheet.data_validation("H%d"%(i+2),{'validate':"list","source":["室内","室外"]})
    for i in range(ord("A"),ord("G")+1):
        worksheet.set_column('%c:%c'%(chr(i),chr(i)),20)
    workbook.close()

# unit test
if __name__ == "__main__":
    print(get_segmentation("static/test2/11_Gadgetbridge..bin",datetime.date(2021,4,11)))