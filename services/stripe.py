import stripe
from config.settings import settings
from fastapi import HTTPException, status

class StripeService:
    def __init__(self):
        # Initialize Stripe with your API key
        stripe.api_key = settings.stripe_secret_key
        # self.price_ids = {
        #     "basic": settings.stripe_basic_price_id,
        #     "premium": settings.stripe_premium_price_id,
        #     "enterprise": settings.stripe_enterprise_price_id
        # }
        
    async def create_customer(self, user_data):
        """Create a Stripe customer for a new user"""
        try:
            customer = stripe.Customer.create(
                email=user_data["email"],
                name=user_data["full_name"],
                metadata={"user_id": user_data["id"]}
            )
            return customer.id
        except Exception as e:
            print(f"Stripe customer creation error: {str(e)}")
            # Don't raise an exception here, just return None
            # so user creation can still succeed even if Stripe fails
            return None
    
    async def create_subscription(self, customer_id, price_id):
        """Create a subscription for a customer"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"],
            )
            return {
                "subscriptionId": subscription.id,
                "clientSecret": subscription.latest_invoice.payment_intent.client_secret
            }
        except Exception as e:
            print(f"Subscription creation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not create subscription: {str(e)}"
            )
    
    async def get_subscription(self, subscription_id):
        """Get details of a subscription"""
        try:
            return stripe.Subscription.retrieve(subscription_id)
        except Exception as e:
            print(f"Error retrieving subscription: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription not found: {str(e)}"
            )
    
    async def cancel_subscription(self, subscription_id):
        """Cancel a subscription"""
        try:
            return stripe.Subscription.delete(subscription_id)
        except Exception as e:
            print(f"Error canceling subscription: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Could not cancel subscription: {str(e)}"
            )
    
    async def update_subscription(self, subscription_id, new_price_id):
        """Update a subscription to a new price/plan"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Update the subscription item with the new price
            updated_subscription = stripe.Subscription.modify(
                subscription_id,
                items=[{
                    'id': subscription['items']['data'][0].id,
                    'price': new_price_id,
                }]
            )
            return updated_subscription
        except Exception as e:
            print(f"Error updating subscription: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not update subscription: {str(e)}"
            )
    
    async def get_customer_invoices(self, customer_id, limit=10):
        """Get recent invoices for a customer"""
        try:
            invoices = stripe.Invoice.list(
                customer=customer_id,
                limit=limit,
                status='paid'
            )
            return invoices
        except Exception as e:
            print(f"Error retrieving invoices: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not retrieve invoices: {str(e)}"
            )
            
    async def get_price_id(self, tier):
        """Get the Stripe price ID for a subscription tier"""
        if tier not in self.price_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid subscription tier: {tier}"
            )
        return self.price_ids[tier]