# services/dynamo.py
import boto3
from botocore.exceptions import ClientError
from typing import Optional, List, Any, Dict
from config.settings import settings

class DynamoDBService:
    def __init__(self):
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
        self.video_table = self.dynamodb.Table('videos')
        self.series_table = self.dynamodb.Table('series')

    async def create_video(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self.video_table.put_item(Item=video_data)
            return video_data
        except ClientError as e:
            raise Exception(f"Could not create video: {str(e)}")

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

    async def list_user_videos(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            response = self.video_table.query(
                KeyConditionExpression='user_id = :user_id',
                ExpressionAttributeValues={
                    ':user_id': user_id
                }
            )
            return response.get('Items', [])
        except ClientError as e:
            raise Exception(f"Could not retrieve videos: {str(e)}")