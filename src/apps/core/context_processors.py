from .permissions import is_creator, is_reviewer

def roles(request):
    return {
        "is_creator": is_creator(request.user),
        "is_reviewer": is_reviewer(request.user),
    }
