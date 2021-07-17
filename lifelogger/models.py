from django.db import models
import numpy as np
import pandas as pd
import os
import sqlite3
from datetime import datetime,timedelta
import zipfile
import re
import json
import shutil
import exifread

# Create your models here.

class User_info(models.Model):
    name = models.CharField(max_length=30,default="root")
    password = models.CharField(max_length=30,default="123456")
    

class SaveFile:
    def __init__(self,user_name, data_path,wrist_file,lifelog_file,print_result = True):
        self.user_name = user_name
        self.DATA_PATH = data_path
        self.wrist_file = wrist_file
        self.lifelog_file = lifelog_file
        self.print_result = print_result
        self.print_str = {}
        self.t_month = datetime.now().month
        self.t_day = datetime.now().day
        self.t_hour = datetime.now().hour
        self.fz_file = "com.java.lifelog_backend"
    
    def prossessing(self):
        self.print_str = {}
        self.get_wrist()
        self.get_lifelog()
        if "error" in self.print_str:
            return self.print_str
        if self.print_result:
            self.test_id()
            self.test_diet()
        self.test_emotion()
        self.test_music()
        self.test_gps()
        self.test_tracer()
        self.get_rec_music()

        return self.print_str

    def get_rec_music(self):
        # todo
        music_pth = "/work/lijiayu/Lifelog/MoodWork/user_study/Music_recommendation/HappyRec/dataset/music/%s/impression.csv"%(self.user_name)
        if not os.path.exists(music_pth):
            self.print_str["rec_music"] = "您没有推荐音乐记录，请联系主试确认原因！\n"
            return
        rec_music = pd.read_csv(music_pth,sep="\t").drop_duplicates()
        rec_num = rec_music.loc[rec_music.stage=="field"].shape[0]
        listen_num = rec_music.loc[(rec_music.stage=="field")&(rec_music.click==1)].shape[0]
        rec_music['date'] = rec_music['timestamp'].apply(lambda x: str((datetime.strptime(x.split(".")[0],"%Y-%m-%d %H:%M:%S")+timedelta(hours=8)).date()))
        self.print_str["rec_music"] = "您共被推荐了%d首歌，听了其中的%d首\n"%(rec_num,listen_num)
        date_rec = rec_music.loc[(rec_music.stage=="field")&(rec_music.click==1)].groupby('date').stage.count().reset_index()
        for i,row in date_rec.iterrows():
            self.print_str['rec_music'] += "您在%s听了%d首歌\n"%(row.date,row.stage)

    def get_wrist(self):
        try:
            con = sqlite3.connect(os.path.join(self.DATA_PATH, self.wrist_file))
            c = con.cursor()
            Activity_data = pd.read_sql("SELECT * FROM MI_BAND_ACTIVITY_SAMPLE",con=con)
            User_attributes = pd.read_sql("SELECT * FROM USER_ATTRIBUTES", con=con)
        except:
            self.print_str["error"] = self.print_str.get("error","") + "手环数据格式有误！\n"
            return

        Activity_data["time"] = Activity_data["TIMESTAMP"].apply(lambda x: datetime.fromtimestamp(x))
        Activity_data["hour"] = Activity_data["time"].apply(lambda x:x.hour)
        Activity_data["date"] = Activity_data["time"].apply(lambda x:x.date())
        # MI_BAND_ACTIVITY_SAMPLE and USER_ATTRIBUTES contain all the data we use
        Activity_data.to_csv(os.path.join(self.DATA_PATH,"%02d%02d-%02d_wrist.csv"%(self.t_month,self.t_day,self.t_hour)),index=False)
        User_attributes.to_csv(os.path.join(self.DATA_PATH,"%02d%02d-%02d_userprofile.csv"%(self.t_month,self.t_day,self.t_hour)),index=False)
        c.close()
        con.close()
        if self.print_result:   
            self.print_str["wrist"] = ""
            All_data = Activity_data.groupby(["date","hour"]).HEART_RATE.count().reset_index()
            Valid_data = Activity_data.loc[Activity_data.HEART_RATE<255].groupby(["date","hour"]).HEART_RATE.count().reset_index()
            All_data.rename(columns={"HEART_RATE":"All_minutes"},inplace=True)
            Valid_data.rename(columns={"HEART_RATE":"Valid_minutes"},inplace=True)
            All_data = All_data.merge(Valid_data,on=["date","hour"],how="left")
            today = (datetime.now()-timedelta(days=1)).date()
            for day in All_data.date.unique():
                all_min = All_data.loc[All_data.date==day].All_minutes.sum()
                valid_min = All_data.loc[All_data.date==day].Valid_minutes.sum()
                self.print_str["wrist"] += ("%s共收集了%.1f时数据，有效数据%.1f时\n"%("-".join(str(day).split("-")[1:]),all_min/60,valid_min/60))

            self.print_str["wrist_today"] = "您在今天每小时收集数据的详情如下："
            for hour in All_data.loc[(All_data.date==today)].hour.unique():
                part = All_data.loc[(All_data.date==today)&(All_data.hour==hour)]
                all_min = part.All_minutes.sum()
                valid_min = part.Valid_minutes.sum()
                if valid_min == 0:
                    continue
                self.print_str["wrist_today"] += ("%02d时 全部数据:%02d分 有效数据:%02d分 (%.2f)\n"%(hour,all_min,valid_min,valid_min/all_min))
                
    def get_lifelog(self):
        fz_name = os.path.join(self.DATA_PATH,self.lifelog_file)
        try:
            with zipfile.ZipFile(fz_name, 'r') as zipf:
                zipf.extractall(self.DATA_PATH)
        except:
            self.print_str["error"] = self.print_str.get("error","") + "App上传.zip压缩文件有误！\n"

    def test_id(self):
        user_id = ""
        bluetooth_id = ""
        setting_file = os.path.join(self.DATA_PATH,self.fz_file,"setting/setting.json")
        if not os.path.exists(setting_file):
            self.print_str["ids"] = "您的用户设置信息不存在，请联系主试确认原因！\n"
            return
        with open(setting_file,"r") as F:
            settings = json.load(F)
            user_id = settings["user_id"]
            bluetooth_id = settings["bluetooth_id"]
        self.print_str["ids"] = ("您的用户id为%s，蓝牙id为%s\n"%(user_id,bluetooth_id))
    
    def test_diet(self):
        diet_dir = os.path.join(self.DATA_PATH,self.fz_file,"image")
        if not os.path.exists(diet_dir):
            self.print_str["diet"] = "您还未上传过食物照片！\n"
        else:
            diet_num = 0
            for image in os.listdir(diet_dir):
                img_size = os.path.getsize(os.path.join(diet_dir,image))
                if img_size>0:
                    diet_num += 1
            self.print_str["diet"] = "您共记录了%d餐的照片。\n"%(diet_num)
    
    def test_emotion(self):
        mood_file = os.path.join(self.DATA_PATH,self.fz_file,"emotion/user_submitted_emotions.txt")
        if not os.path.exists(mood_file):
            self.print_str["mood"] = "您还未上传过情绪数据！\n"
            return
        moods = []
        emotions = []
        with open(mood_file,"r") as F:
            for line in F:
                line = line.strip().split("\t")
                if len(line)<2:
                    continue
                t_type = "m"
                if line[-1]=='e':
                    t_type='e'
                    line = line[:-1]
                time = line[0]
                year, month ,day,hour,minute = [int(x) for x in time.split(":")[:5]]
                if len(line)==3:
                    event = line[1]
                else:
                    event = "record_event"
                valence,arousal = eval(line[-1])
                if t_type=='e':
                    emotions.append([time,event,valence,arousal,year,month,day,hour,minute])
                else:
                    moods.append([time,event,valence,arousal,year,month,day,hour,minute])
        moods = pd.DataFrame(moods,columns=["time","event","valence","arousal","year","month","day","hour","minute"])
        emotions = pd.DataFrame(emotions,columns=["time","event","valence","arousal","year","month","day","hour","minute"])

        moods.to_csv(os.path.join(self.DATA_PATH,"%02d%02d-%02d-mood.csv"%(self.t_month,self.t_day,self.t_hour)),index=False)
        emotions.to_csv(os.path.join(self.DATA_PATH,"%02d%02d-%02d-emotion.csv"%(self.t_month,self.t_day,self.t_hour)),index=False)
        
        if self.print_result:
            self.print_str["mood"] = ""
            self.print_str["mood_event"] = ""
            mood_day = moods.groupby(["month","day"]).valence.count().reset_index().sort_values(by=["month","day"])
            for idx,line in mood_day.iterrows():
                self.print_str["mood"] += ("您在%s月%s日记录了%s条情绪信息\n"%(line.month,line.day,line.valence))
                emotion_day = emotions.groupby(["month","day"]).valence.count().reset_index().sort_values(by=["month","day"])
            for idx,line in emotion_day.iterrows():
                self.print_str["mood"] += ("您在%s月%s日记录了%s条事件和对应的情绪唤起\n"%(line.month,line.day,line.valence))
                for idx2, row in emotions.loc[(emotions.month==line.month)&(emotions.day==line.day)].iterrows():
                    self.print_str["mood_event"] += ("事件：%s\n"%(row.event))
            emotion_arousal = emotions.arousal.mean()
            mood_arousal = moods.arousal.mean()
            if emotion_arousal >= mood_arousal:
                self.print_str["mood_event"] += ("您在突发事件时记录的情绪比一般情况下更强烈\n")
            if emotion_arousal < mood_arousal:
                self.print_str["mood_event"] += ("您在突发事件时记录的情绪并不比一般情况下更强烈\n")

    def test_music(self):
        music_info = []
        this_music = []
        if not os.path.exists(os.path.join(self.DATA_PATH,self.fz_file,"music/musicHistory.txt")):
            self.print_str["music"] = "您还未记录过音乐信息（未使用QQ音乐听过歌）。\n"
            return
        with open(os.path.join(self.DATA_PATH,self.fz_file,"music/musicHistory.txt"),"r") as F:
            for line in F:
                line = line.strip().split("\t")
                if len(line)<2:
                    continue
                song, time = line
                time = datetime.fromtimestamp(int(int(time)/1000))
                year, month,day,hour, minute = time.year, time.month, time.day, time.hour, time.minute
                if len(this_music) and song==this_music[0]:
                    if hour == this_music[-2] and minute-this_music[-1]<=4:
                        continue
                this_music = [song,year,month,day,hour,minute]
                music_info.append(this_music)
        music_info = pd.DataFrame(music_info,columns=["song","year","month","day","hour","minute"])
        music_info.to_csv(os.path.join(self.DATA_PATH,"%02d%02d-%02d-music.csv"%(self.t_month,self.t_day,self.t_hour)),index=False) 
    
        if self.print_result:
            music_day = music_info.groupby(["month","day"]).agg({"song":["count","nunique"]}
                                                   ).reset_index().sort_values(by=["month","day"])
            music_day.columns=["month","day","cnt","unique_song"]
            self.print_str["music"] = ""
            for idx,row in music_day.iterrows():
                self.print_str["music"] += ("您在%d月%d日听了%d首歌，不重复的歌有%d首\n"%(row.month,row.day,row.cnt,row.unique_song)) 

    def test_gps(self):
        # gps：记录了几次GPS的信息
        gps_info = []
        gps_keys = []
        if os.path.exists(os.path.join(self.DATA_PATH,self.fz_file,"gps/gpsInfo.txt"))==0:
            self.print_str["gps"] = "您的GPS与天气信息未记录，请联系主试确认原因！\n"
            return
        with open(os.path.join(self.DATA_PATH,self.fz_file,"gps/gpsInfo.txt"),"r") as F:
            for line in F:
                line = line.strip()
                if len(line)==0:
                    continue
                info = eval(line)
                for key in info:
                    if key not in gps_keys:
                        gps_keys.append(key)
                append_info = []
                for key in gps_keys:
                    append_info.append(info.get(key,-1))
                year, month, day, time = info["timeInfo"].strip().split(",")
                hour,minute = [int(x) for x in time.split(":")[:2]]
                append_info += [int(year),int(month),int(day),int(hour),int(minute)]
                gps_info.append(append_info)
        # weather：记录了几次weather，weather是否是当前城市的
        weather_info = []
        weather_keys = []
        with open(os.path.join(self.DATA_PATH,self.fz_file,"weather/weatherInfo.txt"),"r") as F:
            for line in F:
                line = line.strip()
                if len(line)==0:
                    continue
                info = eval(line)
                for key in info["now"]:
                    if key not in weather_keys:
                        weather_keys.append(key)
                append_info = []
                for key in weather_keys:
                    append_info.append(info["now"].get(key,-1))
                append_info.append(info["timeInfo"])
                year, month, day, time = info["timeInfo"].strip().split(",")
                hour,minute = [int(x) for x in time.split(":")[:2]]
                append_info += [int(year),int(month),int(day),int(hour),int(minute)]
                weather_info.append(append_info)
        gps_info = pd.DataFrame(gps_info,columns=gps_keys+["year","month","day","hour","minute"])
        weather_info = pd.DataFrame(weather_info,columns=weather_keys+["timeInfo","year","month","day","hour","minute"])
        gps_info.to_csv(os.path.join(self.DATA_PATH,"%02d%02d-%02d-gps.csv"%(self.t_month,self.t_day,self.t_hour)),index=False)
        weather_info.to_csv(os.path.join(self.DATA_PATH,"%02d%02d-%02d-weather.csv"%(self.t_month,self.t_day,self.t_hour)),index=False)
        
        if self.print_result:
            self.print_str["gps"] = ""
            gps_day = gps_info.groupby(["month","day"]).longitude.count().reset_index().sort_values(by=["month","day"])
            for idx,line in gps_day.iterrows():
                weather = weather_info.loc[(weather_info.month==line.month)&(weather_info.day==line.day)]
                self.print_str["gps"]+=("您在%s月%s日记录了%s条GPS信息,%d条天气信息\n"%(line.month,line.day,line.longitude,weather.shape[0]))
                part = gps_info.loc[(gps_info.month==line.month)&(gps_info.day==line.day)]
                longitude = (part.longitude.max()-part.longitude.min())*100000
                latitude = (part.latitude.max()-part.latitude.min())*111320
                self.print_str["gps"]+=("--最大移动距离不超过%d米\n"%(max(longitude,latitude)*np.sqrt(2)))
                self.print_str["gps"]+=("--主要天气为%s\n"%(weather.text.value_counts().index[0]))
        
    def test_tracer(self):
        traceInfo = []
        traceKey = ['time','event','moodx','moody']
        traceValue = ['time','event','valence','arousal']
        traceDict = dict(zip(traceKey,traceValue))
        if not os.path.exists(os.path.join(self.DATA_PATH,self.fz_file,"tracer/traceInfo.txt")):
            self.print_str["activity"] = "您还未标注过活动信息，请记得在每天晚上进行标注！\n"
            return
        with open(os.path.join(self.DATA_PATH,self.fz_file,"tracer/traceInfo.txt"),"r") as F:
            for line in F:
                if len(line)<10:
                    continue
                info = eval(line)
                this_date = [int(x) for x in info['timeInfo'].strip().split(" ")[0].split(",")[:3]]
                for activity in info['traceList']:
                    this_info = this_date.copy()
                    for key in traceKey:
                        this_info.append(activity[key])
                    traceInfo.append(this_info)
        traceInfo = pd.DataFrame(traceInfo,columns=["year","month","day"]+traceValue).drop_duplicates()
        traceInfo.to_csv(os.path.join(self.DATA_PATH,"%02d%02d-%02d-trace.csv"%(self.t_month,self.t_day,self.t_hour)),index=False)

        if self.print_result:
            trace_day = traceInfo.groupby(["month","day"]).event.count().reset_index()
            self.print_str["activity"] = ""
            for idx, row in trace_day.iterrows():
                self.print_str["activity"] += ("您在%d月%d日共标注了%d个活动\n"%(row.month,row.day,row.event))

    def calculate_payment(self):
        payment_file = os.path.join(self.DATA_PATH,"payment.xlsx")
        
        music_pth = "/work/lijiayu/Lifelog/MoodWork/user_study/Music_recommendation/HappyRec/dataset/music/%s/impression.csv"%(self.user_name)
        music = pd.read_csv(music_pth,sep="\t")
        music["date"] = music["timestamp"].apply(lambda x: str((datetime.strptime(x.split(".")[0],"%Y-%m-%d %H:%M:%S")+timedelta(hours=8)).date()))
        music_valid = music.loc[(music.stage=='field')&(music.click==1)].groupby('date').i_id_c.nunique().reset_index()
        music_valid["music_pay"] = music_valid["i_id_c"]*5
        payment_df = music_valid[["date","music_pay"]]

        date = "%02d%02d-%02d"%(self.t_month,self.t_day,self.t_hour)
        if os.path.exists(os.path.join(self.DATA_PATH,date+"-trace.csv")):
            traceInfo = pd.read_csv(os.path.join(self.DATA_PATH,date+"-trace.csv"))
            trace_valid = traceInfo.groupby(["month","day"]).event.count().reset_index()
            trace_valid["date"] = trace_valid.apply(lambda x: "2021-%02d-%02d"%(x.month,x.day),axis=1)
            trace_valid["activity_pay"] = trace_valid["event"].apply(lambda x: 10 if x>5 else 0)
            payment_df = payment_df.merge(trace_valid[['date','activity_pay']],on='date',how="outer")

        img_path = os.path.join(self.DATA_PATH,self.fz_file,"image")
        img_timedict = {}
        if os.path.exists(img_path):
            for img_name in os.listdir(img_path):
                img=exifread.process_file(open(os.path.join(img_path,img_name),'rb'))
                if "Image DateTime" in img:
                    time=img['Image DateTime']
                    day = str(datetime.strptime(str(time),"%Y:%m:%d %H:%M:%S").date())
                    img_timedict[day] = img_timedict.get(day,0) + 1
        if len(img_timedict):    
            img_valid = pd.DataFrame.from_dict(img_timedict,orient='index').reset_index()
            img_valid.columns=["date","img_num"]
            img_valid["img_pay"] = img_valid['img_num'] * 2
            payment_df = payment_df.merge(img_valid[['date','img_pay']],on='date',how="outer")

        payment_df.fillna(0,inplace=True)
        payment_df["basic"] = 15
        payment_df["sum"] = payment_df.drop(columns=["date"]).apply(lambda x: x.sum() if x.sum()<=60 else 60, axis=1)

        payment_df.to_excel(payment_file,index=False)
        return "payment.xlsx" 

    def del_file(self, file):
        if os.path.exists(file):
            try:
                os.remove(file)
            except:
                shutil.rmtree(file)
        print("Successfully delete "+ file)

    def delete(self, delete_list):
        self.del_file(os.path.join(self.DATA_PATH,self.wrist_file))
        self.del_file(os.path.join(self.DATA_PATH,self.lifelog_file))
        date = "%02d%02d-%02d"%(self.t_month,self.t_day,self.t_hour)
        for delete_type in delete_list:
            if delete_type == 'id' :
	            self.del_file(os.path.join(self.DATA_PATH,self.fz_file,'setting'))
            elif delete_type == 'wrist' :
                self.del_file(os.path.join(self.DATA_PATH,"%s_wrist.csv"%(date)))
                self.del_file(os.path.join(self.DATA_PATH,"%s_userprofile.csv"%(date)))
            elif delete_type == 'mood':
                self.del_file(os.path.join(self.DATA_PATH,"%s-mood.csv"%(date)))
                self.del_file(os.path.join(self.DATA_PATH,"%s-emotion.csv"%(date)))
                self.del_file(os.path.join(self.DATA_PATH,self.fz_file,'emotion'))
            elif delete_type == 'gps':
                self.del_file(os.path.join(self.DATA_PATH,"%s-gps.csv"%(date)))
                self.del_file(os.path.join(self.DATA_PATH,"%s-weather.csv"%(date)))
                self.del_file(os.path.join(self.DATA_PATH,self.fz_file,'gps'))
                self.del_file(os.path.join(self.DATA_PATH,self.fz_file,'weather'))
            elif delete_type == 'diet':
                self.del_file(os.path.join(self.DATA_PATH,self.fz_file,'image'))
            elif delete_type == 'music':
                self.del_file(os.path.join(self.DATA_PATH,self.fz_file,'music'))
                self.del_file(os.path.join(self.DATA_PATH,"%s-music.csv"%(date)))
            elif delete_type == 'act':
                self.del_file(os.path.join(self.DATA_PATH,self.fz_file,'tracer'))
                self.del_file(os.path.join(self.DATA_PATH,"%s-trace.csv"%(date)))

# unit test
if __name__ == '__main__':
    user_info = User_info()