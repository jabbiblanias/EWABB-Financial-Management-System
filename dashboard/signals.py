from django.dispatch import receiver
from django.contrib.auth.models import User
from dashboard.models import CashierStatus
from django.db.models.signals import post_save, m2m_changed
from django.contrib.auth.models import Group


@receiver(post_save, sender=User)
def create_cashier_status_on_new_user(sender, instance, created, **kwargs):
    """
    Creates a CashierStatus instance automatically only when a new User is created 
    and they are already in the 'Cashier' group (e.g., via fixtures or initial admin screen).
    """
    if created:
        # Check if the new user belongs to the 'Cashier' group
        if instance.groups.filter(name='Cashier').exists():
            try:
                # Use get_or_create to prevent race conditions if possible, though less critical here
                CashierStatus.objects.get_or_create(user_id=instance, defaults={'status': 'available'})
                print(f"Created CashierStatus for new user: {instance.username}")
            except Exception as e:
                print(f"Error creating CashierStatus for user {instance.username}: {e}")

@receiver(m2m_changed, sender=User.groups.through)
def manage_cashier_status_on_group_change(sender, instance, action, reverse, model, pk_set, **kwargs):
    """
    Manages the CashierStatus when a user is added to or removed from groups.
    This runs when editing groups on an existing user.
    """
    # We only care about users being added to or removed from groups
    if action in ['post_add', 'post_remove']:
        
        try:
            cashier_group = Group.objects.get(name='Cashier')
        except Group.DoesNotExist:
            return # Exit if the group doesn't exist

        # 1. Check if the 'Cashier' group was involved in the change
        if cashier_group.pk in pk_set:
            
            is_cashier = instance.groups.filter(name='Cashier').exists()

            if action == 'post_add' and is_cashier:
                # User was just added to the group
                CashierStatus.objects.get_or_create(user_id=instance, defaults={'status': 'available'})
                print(f"Created CashierStatus via group assignment for: {instance.username}")

            elif action == 'post_remove' and not is_cashier:
                # User was just removed from the group, so delete the status record
                try:
                    CashierStatus.objects.filter(user_id=instance).delete()
                    print(f"Deleted CashierStatus after group removal for: {instance.username}")
                except CashierStatus.DoesNotExist:
                    pass # Already gone, nothing to do
