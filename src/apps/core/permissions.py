from django.contrib.auth.models import Group

def in_group(user, group_name: str) -> bool:
    if not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()

def is_creator(user) -> bool:
    return in_group(user, "creador")

def is_reviewer(user) -> bool:
    return in_group(user, "revisor")

def is_approver(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.groups.filter(name__iexact="aprobador").exists()

