import boto3
from botocore.exceptions import ClientError
from typing import Optional, List, Any, Dict
from datetime import datetime, timezone
from config.settings import settings
from models.videos import VideoStatus, VideoDetail, GeneratedImage, ImagePrompt
from uuid import uuid4

class DynamoDBService:
    def __init__(self):
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
        self.video_table = self.dynamodb.Table('instashorts_videos')
        self.series_table = self.dynamodb.Table('instashorts_series')
        self.users_table = self.dynamodb.Table('instashorts_users')


    '''VIDEO RELATED OPERATIONS'''
    def create_video(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new video entry in DynamoDB with initial fields"""
        video_item = {
            'id': str(uuid4()),
            'user_id': video_data['user_id'],
            'topic': video_data['topic'],
            'voice': video_data['voice'],
            'creation_status': VideoStatus.PENDING.value,
            'title': '',  # Will be populated by script generation
            'script': '',  # Will be populated by script generation
            'series': video_data.get('series', None),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }

        try:
            self.video_table.put_item(Item=video_item)
            return video_item
        except ClientError as e:
            raise Exception(f"Could not create video: {str(e)}")
        
        
    def get_user_videos(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all videos for a user with only list view fields"""
        try:
            query_params = {
                'IndexName': 'user-videos-index',
                'KeyConditionExpression': '#uid = :uid',
                'ExpressionAttributeNames': {
                    '#uid': 'user_id'
                },
                'ExpressionAttributeValues': {
                    ':uid': user_id
                },
                'ProjectionExpression': 'id, user_id, topic, voice, title, creation_status, final_url, series, created_at, video_url',
                'ScanIndexForward': False,
                'Limit': 20
            }
            
            
            response = self.video_table.query(**query_params)
            return response.get('Items', [])
        except ClientError as e:
            raise Exception(f"Could not retrieve videos: {str(e)}")
        
        
    def get_video(self, video_id: str, user_id: str):
        try:
            response = self.video_table.get_item(
                Key={
                    'id': video_id
                }
            )
            item = response.get('Item')
            if item and item.get('user_id') != user_id:
                raise Exception("User not authorized to access this video")
            return item
        except ClientError as e:
            raise Exception(f"Could not retrieve video: {str(e)}")


    def update_video(self, video_id: str, update_data: Dict[str, Any]) -> VideoDetail:
        update_expression = "SET "
        expression_attribute_values = {}
        expression_attribute_names = {}
        
        # Add ExpressionAttributeNames to handle reserved words
        for key in update_data.keys():
            update_expression += f"#{key} = :{key}, "
            expression_attribute_values[f":{key}"] = update_data[key]
            expression_attribute_names[f"#{key}"] = key

        update_expression = update_expression.rstrip(", ")
        
        try:
            response = self.video_table.update_item(
                Key={
                    'id': video_id
                },
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_attribute_values,
                ExpressionAttributeNames=expression_attribute_names,
                ReturnValues="ALL_NEW"
            )
            
            # Convert DynamoDB response to VideoDetail
            video_data = response.get('Attributes', {})
            
            # Convert image prompts and generated images if they exist
            img_prompts = None
            if 'img_prompts' in video_data:
                img_prompts = [ImagePrompt(index=p['index'], prompt=p['prompt']) 
                            for p in video_data['img_prompts']]
                
            images = None
            if 'images' in video_data:
                images = [GeneratedImage(index=img['index'], url=img['url']) 
                        for img in video_data['images']]
            
            # Create VideoDetail object with all fields
            return VideoDetail(
                id=video_data['id'],
                user_id=video_data['user_id'],
                topic=video_data['topic'],
                voice=video_data['voice'],
                creation_status=VideoStatus(video_data['creation_status']).value,
                title=video_data.get('title'),
                series=video_data.get('series'),
                script=video_data['script'],
                img_prompts=img_prompts,
                audio_url=video_data.get('audio_url'),
                images=images,
                final_url=video_data.get('final_url'),
                created_at=video_data['created_at']
            )
                
        except ClientError as e:
            raise Exception(f"Could not update video: {str(e)}")


    def delete_video(self, video_id: str, user_id: str) -> bool:
        try:
            self.video_table.delete_item(
                Key={
                    'id': video_id,
                    'user_id': user_id
                }
            )
            return True
        except ClientError as e:
            raise Exception(f"Could not delete video: {str(e)}")


    '''USER RELATED DYNAMO OPERATIONS'''
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.users_table.get_item(
                Key={'id': user_id}
            )
            return response.get('Item')
        except ClientError as e:
            raise Exception(f"Could not retrieve user: {str(e)}")



    async def create_or_update_user(self, user_data: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
        # Import the Stripe service here to avoid circular imports
        from services.stripe import StripeService
        stripe_service = StripeService()
        
        is_new_user = False
        existing_user = await self.get_user(user_data['id'])
        current_time = datetime.now(timezone.utc).isoformat()

        try:
            if not existing_user:
                is_new_user = True
                
                # For new users, create a Stripe customer
                stripe_customer_id = await stripe_service.create_customer(user_data)
                
                # Prepare user data with Stripe info and default subscription values
                new_user_data = {
                    'id': user_data['id'],
                    'email': user_data['email'],
                    'full_name': user_data['full_name'],
                    'picture': user_data.get('picture', ''),
                    'last_login': current_time,
                    'created_at': current_time,
                    'updated_at': current_time,
                    'stripe_customer_id': stripe_customer_id,
                    'subscription_tier': 'free',
                    'active_subscription': False
                }
                
                self.users_table.put_item(Item=new_user_data)
                user_data = new_user_data
            else:
                # For existing users, preserve subscription and Stripe data
                self.users_table.update_item(
                    Key={'id': user_data['id']},
                    UpdateExpression="""
                        set email=:email,
                            full_name=:full_name,
                            picture=:picture,
                            last_login=:last_login,
                            updated_at=:updated_at
                    """,
                    ExpressionAttributeValues={
                        ':email': user_data['email'],
                        ':full_name': user_data['full_name'],
                        ':picture': user_data.get('picture', ''),
                        ':last_login': current_time,
                        ':updated_at': current_time
                    }
                )
                
                # Add existing user's Stripe and subscription data to the returned user_data
                if existing_user.get('stripe_customer_id'):
                    user_data['stripe_customer_id'] = existing_user['stripe_customer_id']
                if existing_user.get('subscription_tier'):
                    user_data['subscription_tier'] = existing_user['subscription_tier']
                if existing_user.get('active_subscription'):
                    user_data['active_subscription'] = existing_user['active_subscription']
                if existing_user.get('subscription_id'):
                    user_data['subscription_id'] = existing_user['subscription_id']
                
            return user_data, is_new_user
        except ClientError as e:
            raise Exception(f"Could not create/update user: {str(e)}")
        
    async def find_user_by_stripe_customer_id(self, stripe_customer_id: str) -> Optional[Dict[str, Any]]:
        """Find a user by their Stripe customer ID"""
        try:
            # Use a scan operation with a filter expression
            # Note: In a production environment with many users, you should create
            # a global secondary index on stripe_customer_id for better performance
            response = self.users_table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('stripe_customer_id').eq(stripe_customer_id)
            )
            
            items = response.get('Items', [])
            if items:
                # Return the first matching user
                return items[0]
            return None
        except ClientError as e:
            print(f"Error finding user by Stripe customer ID: {str(e)}")
            return None
        
    
    async def create_series(self, series_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self.series_table.put_item(Item=series_data)
            return series_data
        except ClientError as e:
            raise Exception(f"Could not create series: {str(e)}")

    async def get_series(self, series_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.series_table.get_item(
                Key={
                    'id': series_id,
                    'user_id': user_id
                }
            )
            return response.get('Item')
        except ClientError as e:
            raise Exception(f"Could not retrieve series: {str(e)}")
