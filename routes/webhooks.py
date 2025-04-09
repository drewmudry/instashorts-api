import stripe
from fastapi import APIRouter, Request, HTTPException, status
from config.settings import settings
from services.dynamo import DynamoDBService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
dynamo_service = DynamoDBService()

@router.post("/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        # Verify the event came from Stripe
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        raise HTTPException(status_code=400, detail=str(e))
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise HTTPException(status_code=400, detail=str(e))

    # Handle the event based on its type
    if event["type"] == "checkout.session.completed":
        print("Checkout session completed")
        # Process the checkout (could be a new subscription)
        session = event["data"]["object"]
        await process_checkout_session(session)
        
    elif event["type"] == "customer.subscription.created":
        print("Subscription created")
        # Handle new subscription
        subscription = event["data"]["object"]
        await handle_subscription_created(subscription)
        
    elif event["type"] == "customer.subscription.updated":
        print("Subscription updated")
        # Handle subscription update
        subscription = event["data"]["object"]
        await handle_subscription_updated(subscription)
        
    elif event["type"] == "customer.subscription.deleted":
        print("Subscription deleted")
        # Handle subscription cancellation
        subscription = event["data"]["object"]
        await handle_subscription_deleted(subscription)
        
    elif event["type"] == "invoice.payment_succeeded":
        print("Invoice payment succeeded")
        # Handle successful payment
        invoice = event["data"]["object"]
        await handle_payment_succeeded(invoice)
        
    elif event["type"] == "invoice.payment_failed":
        print("Invoice payment failed")
        # Handle failed payment
        invoice = event["data"]["object"]
        await handle_payment_failed(invoice)
    
    # Return a 200 response to acknowledge receipt of the event
    return {"status": "success"}

async def process_checkout_session(session):
    """Process a completed checkout session"""
    # Implement your checkout session processing logic here
    customer_id = session.get("customer")
    if not customer_id:
        return
    
    # Find the user with this Stripe customer ID
    user = await dynamo_service.find_user_by_stripe_customer_id(customer_id)
    if not user:
        return
    
    # If it was a subscription checkout, update the user's subscription
    subscription_id = session.get("subscription")
    if subscription_id:
        await dynamo_service.update_user_fields(
            user["id"],
            {
                "subscription_id": subscription_id,
                "active_subscription": True
            }
        )

async def handle_subscription_created(subscription):
    """Handle a new subscription"""
    customer_id = subscription.get("customer")
    if not customer_id:
        return
    
    # Find the user with this Stripe customer ID
    user = await dynamo_service.find_user_by_stripe_customer_id(customer_id)
    if not user:
        return
    
    # Determine the tier based on price
    tier = "basic"  # Default tier
    items = subscription.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")
        # Match price ID to tier
        if price_id == settings.stripe_premium_price_id:
            tier = "premium"
        elif price_id == settings.stripe_enterprise_price_id:
            tier = "enterprise"
    
    # Update user with subscription info
    await dynamo_service.update_user_fields(
        user["id"],
        {
            "subscription_id": subscription.get("id"),
            "subscription_tier": tier,
            "active_subscription": subscription.get("status") == "active"
        }
    )

async def handle_subscription_updated(subscription):
    """Handle an updated subscription"""
    # Similar to subscription created
    customer_id = subscription.get("customer")
    if not customer_id:
        return
    
    # Find the user with this Stripe customer ID
    user = await dynamo_service.find_user_by_stripe_customer_id(customer_id)
    if not user:
        return
    
    # Determine the tier based on price
    tier = "basic"  # Default tier
    items = subscription.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")
        # Match price ID to tier
        if price_id == settings.stripe_premium_price_id:
            tier = "premium"
        elif price_id == settings.stripe_enterprise_price_id:
            tier = "enterprise"
    
    # Update user with subscription info
    await dynamo_service.update_user_fields(
        user["id"],
        {
            "subscription_tier": tier,
            "active_subscription": subscription.get("status") == "active"
        }
    )

async def handle_subscription_deleted(subscription):
    """Handle a cancelled subscription"""
    customer_id = subscription.get("customer")
    if not customer_id:
        return
    
    # Find the user with this Stripe customer ID
    user = await dynamo_service.find_user_by_stripe_customer_id(customer_id)
    if not user:
        return
    
    # Update user to remove subscription
    await dynamo_service.update_user_fields(
        user["id"],
        {
            "subscription_id": None,
            "subscription_tier": "free",
            "active_subscription": False
        }
    )

async def handle_payment_succeeded(invoice):
    """Handle a successful payment"""
    # You might want to log this or send a receipt email
    customer_id = invoice.get("customer")
    if not customer_id:
        return
    
    # Find the user with this Stripe customer ID
    user = await dynamo_service.find_user_by_stripe_customer_id(customer_id)
    if not user:
        return
    
    # Make sure their subscription is marked as active
    if invoice.get("subscription"):
        await dynamo_service.update_user_field(
            user["id"], "active_subscription", True
        )

async def handle_payment_failed(invoice):
    """Handle a failed payment"""
    customer_id = invoice.get("customer")
    if not customer_id:
        return
    
    # Find the user with this Stripe customer ID
    user = await dynamo_service.find_user_by_stripe_customer_id(customer_id)
    if not user:
        return
    
    # You might want to send an email to the user about the failed payment
    
    # If the subscription is going to be canceled due to failed payment,
    # you might want to update the user's subscription status
    # This depends on your Stripe settings for failed payments