from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard' # Replace 'yourapp' with your actual app name

    def ready(self):
        # Import the signals module here to connect the receivers
        import dashboard.signals # Change 'yourapp' to your app's name
