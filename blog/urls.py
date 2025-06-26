from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    # Blog home
    path('', views.blog_home, name='home'),
    
    # Article list
    path('articles/', views.article_list, name='article_list'),
    
    # Individual article
    path('article/<slug:slug>/', views.article_detail, name='article_detail'),
] 