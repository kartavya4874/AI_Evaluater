from datetime import datetime
from bson import ObjectId
from utils.db_connection import db_connection

class Evaluation:
    @staticmethod
    def get_collection():
        """Get evaluations collection with lazy connection"""
        return db_connection.get_collection('evaluations')
    
    @staticmethod
    def create(teacher_id, student_id, question, model_answer, student_answer, 
               extracted_text, max_marks, evaluation_result, teacher_name=None, 
               student_name=None, student_rollno=None):
        """Create a new evaluation record"""
        evaluation = {
            'teacher_id': teacher_id,
            'teacher_name': teacher_name,
            'student_id': student_id,
            'student_name': student_name,
            'student_rollno': student_rollno,
            'question': question,
            'model_answer': model_answer,
            'student_answer': student_answer,
            'extracted_text': extracted_text,
            'max_marks': max_marks,
            'marks': evaluation_result.get('marks_awarded', 0),
            'percentage': evaluation_result.get('percentage', 0),
            'grade': evaluation_result.get('grade', 'N/A'),
            'strengths': evaluation_result.get('strengths', []),
            'missing_points': evaluation_result.get('missing_points', []),
            'feedback': evaluation_result.get('feedback', ''),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        result = Evaluation.get_collection().insert_one(evaluation)
        evaluation['_id'] = result.inserted_id
        return evaluation
    
    @staticmethod
    def find_by_id(evaluation_id):
        """Find evaluation by ID"""
        return Evaluation.get_collection().find_one({'_id': ObjectId(evaluation_id)})
    
    @staticmethod
    def find_by_student(student_id, limit=10):
        """Find evaluations by student ID"""
        return list(Evaluation.get_collection().find({'student_id': student_id})
                   .sort('created_at', -1)
                   .limit(limit))
    
    @staticmethod
    def find_by_teacher(teacher_id, limit=10):
        """Find evaluations by teacher ID"""
        return list(Evaluation.get_collection().find({'teacher_id': teacher_id})
                   .sort('created_at', -1)
                   .limit(limit))
    
    @staticmethod
    def get_student_statistics(student_id):
        """Get statistics for a student"""
        pipeline = [
            {'$match': {'student_id': student_id}},
            {'$group': {
                '_id': None,
                'total_evaluations': {'$sum': 1},
                'average_marks': {'$avg': '$marks_awarded'},
                'average_percentage': {'$avg': '$percentage'},
                'total_marks': {'$sum': '$marks_awarded'},
                'max_possible_marks': {'$sum': '$max_marks'}
            }}
        ]
        
        result = list(Evaluation.get_collection().aggregate(pipeline))
        return result[0] if result else None
    
    @staticmethod
    def get_recent_evaluations(limit=20):
        """Get recent evaluations across all students"""
        return list(Evaluation.get_collection().find()
                   .sort('created_at', -1)
                   .limit(limit))
    
    @staticmethod
    def delete(evaluation_id):
        """Delete an evaluation"""
        return Evaluation.get_collection().delete_one({'_id': ObjectId(evaluation_id)})
    
    @staticmethod
    def get_all():
        """Get all evaluations"""
        return list(Evaluation.get_collection().find().sort('created_at', -1))

    # ==================== BATCH PROCESSING METHODS ====================

    @staticmethod
    def create_batch(course_code, roll_number, model_answer, student_answer,
                     extracted_text, max_marks, evaluation_result):
        """Create a new evaluation record for batch processing (no teacher/student roles)."""
        evaluation = {
            'course_code': course_code,
            'roll_number': roll_number,
            'batch_mode': True,
            'question': '',
            'model_answer': model_answer,
            'student_answer': student_answer,
            'extracted_text': extracted_text,
            'max_marks': max_marks,
            'marks': evaluation_result.get('marks_awarded', 0),
            'percentage': evaluation_result.get('percentage', 0),
            'grade': evaluation_result.get('grade', 'N/A'),
            'strengths': evaluation_result.get('strengths', []),
            'missing_points': evaluation_result.get('missing_points', []),
            'feedback': evaluation_result.get('feedback', ''),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }

        result = Evaluation.get_collection().insert_one(evaluation)
        evaluation['_id'] = result.inserted_id
        return evaluation

    @staticmethod
    def find_by_course(course_code):
        """Find all evaluations for a specific course code."""
        return list(Evaluation.get_collection().find(
            {'course_code': course_code}
        ).sort('roll_number', 1))

    @staticmethod
    def find_by_roll_number(roll_number):
        """Find all evaluations for a specific roll number across all courses."""
        return list(Evaluation.get_collection().find(
            {'roll_number': roll_number}
        ).sort('created_at', -1))

    @staticmethod
    def find_by_course_and_roll(course_code, roll_number):
        """Find evaluation for a specific course + roll number."""
        return Evaluation.get_collection().find_one({
            'course_code': course_code,
            'roll_number': roll_number
        })

    @staticmethod
    def get_batch_evaluations(limit=100):
        """Get all batch evaluations."""
        return list(Evaluation.get_collection().find(
            {'batch_mode': True}
        ).sort('created_at', -1).limit(limit))

    @staticmethod
    def get_course_statistics(course_code):
        """Get statistics for a specific course."""
        pipeline = [
            {'$match': {'course_code': course_code, 'batch_mode': True}},
            {'$group': {
                '_id': None,
                'total_students': {'$sum': 1},
                'average_marks': {'$avg': '$marks'},
                'average_percentage': {'$avg': '$percentage'},
                'max_score': {'$max': '$marks'},
                'min_score': {'$min': '$marks'},
                'total_marks_possible': {'$first': '$max_marks'}
            }}
        ]
        result = list(Evaluation.get_collection().aggregate(pipeline))
        return result[0] if result else None

