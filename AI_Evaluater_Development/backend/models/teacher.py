from datetime import datetime
from bson import ObjectId
from utils.db_connection import db_connection

class Teacher:
    @staticmethod
    def get_collection():
        """Get teachers collection with lazy connection"""
        return db_connection.get_collection('teachers')
    
    @staticmethod
    def create(name, email, subject=None):
        """Create a new teacher"""
        teacher = {
            'name': name,
            'email': email,
            'subject': subject,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        result = Teacher.get_collection().insert_one(teacher)
        teacher['_id'] = result.inserted_id
        return teacher
    
    @staticmethod
    def find_by_email(email):
        """Find teacher by email"""
        return Teacher.get_collection().find_one({'email': email})
    
    @staticmethod
    def find_by_id(teacher_id):
        """Find teacher by ID"""
        return Teacher.get_collection().find_one({'_id': ObjectId(teacher_id)})
    
    @staticmethod
    def update(teacher_id, data):
        """Update teacher information"""
        data['updated_at'] = datetime.utcnow()
        return Teacher.get_collection().update_one(
            {'_id': ObjectId(teacher_id)},
            {'$set': data}
        )
    
    @staticmethod
    def get_all():
        """Get all teachers"""
        return list(Teacher.get_collection().find())
    
    @staticmethod
    def delete(teacher_id):
        """Delete a teacher"""
        return Teacher.get_collection().delete_one({'_id': ObjectId(teacher_id)})
