from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .serializers import UserRegisterSerializer

User = get_user_model()

class PublicUserRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        required_fields = ['username', 'email', 'password']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return Response({'error': f'Missing required fields: {", ".join(missing)}'}, status=400)

        if User.objects.filter(email=data['email']).exists():
            return Response({'error': 'User with this email already exists'}, status=400)
        if User.objects.filter(username=data['username']).exists():
            return Response({'error': 'Username already taken'}, status=400)

        serializer = UserRegisterSerializer(data={
            'username': data['username'],
            'email': data['email'],
            'password': data['password']
        })
        if serializer.is_valid():
            user = serializer.save()
            return Response({'user': serializer.data, 'message': 'Registration successful!'}, status=201)
        return Response(serializer.errors, status=400)
