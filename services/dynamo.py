import boto3
from botocore.exceptions import ClientError
from typing import Optional, List, Any, Dict
from datetime import datetime, timezone
from config.settings import settings
from models.videos import VideoStatus
import uuid

class DynamoDBService:
    def __init__(self):
        region = "us-east-1"
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
            # region_name=region
        )
        self.video_table = self.dynamodb.Table('instashorts_videos')
        self.series_table = self.dynamodb.Table('instashorts_series')
        self.users_table = self.dynamodb.Table('instashorts_users')


    async def create_video(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new video entry in DynamoDB with initial fields"""
        video_item = {
            'id': str(uuid.uuid4()),
            'user_id': video_data['user_id'],
            'theme': video_data['theme'],
            'voice': video_data['voice'],
            'creation_status': VideoStatus.PENDING,
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
        
        
    async def get_user_videos(self, user_id: str) -> List[Dict[str, Any]]:
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
                'ProjectionExpression': 'id, user_id, theme, voice, title, creation_status, final_url, series, created_at',
                'ScanIndexForward': False,
                'Limit': 20
            }

            response = self.video_table.query(**query_params)
            return response.get('Items', [])  # Just return the items list
        except ClientError as e:
            raise Exception(f"Could not retrieve videos: {str(e)}")
        
        
    async def get_video(self, video_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a single video with all fields"""
        try:
            response = self.video_table.get_item(
                Key={
                    'id': video_id,
                    'user_id': user_id
                }
            )
            return response.get('Item')
        except ClientError as e:
            raise Exception(f"Could not retrieve video: {str(e)}")
     
            
    async def create_or_update_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self.users_table.put_item(Item={
                'id': user_data['id'],
                'email': user_data['email'],
                'full_name': user_data['full_name'],
                'picture': user_data.get('picture', ''),
                'last_login': datetime.now(timezone.utc).isoformat(),
                'created_at': user_data.get('created_at', datetime.now(timezone.utc).isoformat()),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            return user_data
        except ClientError as e:
            raise Exception(f"Could not create/update user: {str(e)}")
        
       
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.users_table.get_item(
                Key={'id': user_id}
            )
            return response.get('Item')
        except ClientError as e:
            raise Exception(f"Could not retrieve user: {str(e)}")

    async def update_video(self, video_id: str, user_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        update_expression = "SET "
        expression_attribute_values = {}
        
        for key, value in update_data.items():
            update_expression += f"#{key} = :{key}, "
            expression_attribute_values[f":{key}"] = value

        update_expression = update_expression.rstrip(", ")
        
        try:
            response = self.video_table.update_item(
                Key={
                    'id': video_id,
                    'user_id': user_id
                },
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW"
            )
            return response.get('Attributes', {})
        except ClientError as e:
            raise Exception(f"Could not update video: {str(e)}")

    async def delete_video(self, video_id: str, user_id: str) -> bool:
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
