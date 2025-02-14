import boto3
from botocore.exceptions import ClientError
from typing import Optional, List, Any, Dict
from datetime import datetime, timezone
from config.settings import settings

class DynamoDBService:
    def __init__(self):
        region = "us-east-1"
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            # region_name=settings.aws_region
            region_name=region
        )
        self.video_table = self.dynamodb.Table('instashorts_videos')
        self.series_table = self.dynamodb.Table('instashorts_series')
        self.users_table = self.dynamodb.Table('instashorts_users')

    async def create_video(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new video entry in DynamoDB"""
        required_fields = {
            'id': video_data['id'],
            'user_id': video_data['user_id'],
            'title': video_data['title'],
            'status': video_data['status'],
            'created_at': video_data.get('created_at', datetime.now(timezone.utc).isoformat()),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        video_item = {
            **required_fields,
            'description': video_data.get('description', ''),
            'script': video_data.get('script', ''),
            'voice_file_url': video_data.get('voice_file_url', ''),
            'image_prompts': video_data.get('image_prompts', []),
            'image_urls': video_data.get('image_urls', []),
            'final_video_url': video_data.get('final_video_url', ''),
            'series_id': video_data.get('series_id', ''),
            'error': video_data.get('error', '')
        }

        try:
            self.video_table.put_item(Item=video_item)
            return video_item
        except ClientError as e:
            raise Exception(f"Could not create video: {str(e)}")
        
    async def get_user_videos(self, user_id: str, last_evaluated_key: Optional[Dict] = None) -> Dict[str, Any]:
        """Get all videos for a user with pagination"""
        try:
            print("getting query params")
            query_params = {
                'IndexName': 'user-videos-index',
                'KeyConditionExpression': '#uid = :uid',
                'ExpressionAttributeNames': {
                    '#uid': 'user_id'
                },
                'ExpressionAttributeValues': {
                    ':uid': user_id
                },
                'ScanIndexForward': False,
                'Limit': 20
            }

            if last_evaluated_key:
                query_params['ExclusiveStartKey'] = last_evaluated_key
            print(query_params)
            print("trying to query table")
            response = self.video_table.query(**query_params)
            return {
                'items': response.get('Items', []),
                'last_evaluated_key': response.get('LastEvaluatedKey')
            }
        except ClientError as e:
            raise Exception(f"Could not retrieve videos: {str(e)}")
            
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

    async def get_video(self, video_id: str, user_id: str) -> Optional[Dict[str, Any]]:
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

    # Similar methods for Series
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
