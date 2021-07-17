from django.urls import path
from . import views

app_name = 'lifelogger'
urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('register', views.register, name='register'),
    path('preference&name=<str:user_name>', views.preference, name='preference'),
    path('preference_remain&name=<str:user_name>', views.preference_remain, name='preference_remain'),
    path('preference_start&name=<str:user_name>', views.preference_start, name='preference_start'),
    path('recommendation&name=<str:user_name>',views.recommendation, name='recommendation'),
    path('train',views.train_model, name='train'),
    # path('^uploadfile/(?P<str:user_name>)$',views.uploadfile,name="uploadfile"),
    path('uploadfile&name=<str:user_name>',views.uploadfile,name="uploadfile"),
    path('downloadfile&name=<str:user_name>&file=<str:segment_file>',views.downloadfile,name="downloadfile"),
    path('uploadtable&name=<str:user_name>',views.uploadtable,name="uploadtable"),
    path('thanks',views.thanks,name="thanks"),
    path("labelmood&name=<str:user_name>",views.labelmood,name="labelmood"),
    path("datatest&name=<str:user_name>",views.datatest,name="datatest"),
    path("dataverify&name=<str:user_name>&file=<str:wrist_filename>&<str:lifelog_filename>",views.dataverify,name="dataverify"),
    path("verifydone&name=<str:user_name>&file=<str:file>",views.verifydone,name='verifydone')
]
