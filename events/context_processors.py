from django.contrib.auth import get_user_model

def user_exists_processor(request):
    User = get_user_model()
    users_exist = User.objects.exists()
    return {'users_exist': users_exist} 