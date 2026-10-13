from datetime import datetime
from bson import ObjectId
from utils.db_connection import db_connection

class Student:
    @staticmethod
    def get_collection():
        """Get students collection with lazy connection"""
        return db_connection.get_collection('students')
    
    @staticmethod
    def create(name, email, roll_number=None, class_name=None):
        """Create a new student"""
        student = {
            'name': name,
            'email': email,
            'roll_number': roll_number,
            'class': class_name,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        result = Student.get_collection().insert_one(student)
        student['_id'] = result.inserted_id
        return student
    
    @staticmethod
    def find_by_email(email):
        """Find student by email"""
        return Student.get_collection().find_one({'email': email})
    
    @staticmethod
    def find_by_id(student_id):
        """Find student by ID"""
        return Student.get_collection().find_one({'_id': ObjectId(student_id)})
    
    @staticmethod
    def find_by_roll_number(roll_number):
        """Find student by roll number"""
        return Student.get_collection().find_one({'roll_number': roll_number})
    
    @staticmethod
    def update(student_id, data):
        """Update student information"""
        data['updated_at'] = datetime.utcnow()
        return Student.get_collection().update_one(
            {'_id': ObjectId(student_id)},
            {'$set': data}
        )
    
    @staticmethod
    def get_all():
        """Get all students"""
        return list(Student.get_collection().find())
    
    @staticmethod
    def delete(student_id):
        """Delete a student"""
        return Student.get_collection().delete_one({'_id': ObjectId(student_id)})
