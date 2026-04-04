# AI Examiner Backend - Multi-Course Scaling with Multithreading

## Project Overview
Refactor the AI Examiner backend to process multiple course codes (e.g., MB3103, CH3501) in parallel, where each course contains:
- 1 model answer PDF
- Multiple student answer sheets

## Current Architecture
- Single course processing workflow
- Sequential PDF processing and evaluation
- API-driven endpoints

## Target Architecture
```
root_folder/
├── config.json                 # Contains max_marks (applied to all evaluations)
├── MB3103/
│   ├── model_answer.pdf
│   ├── 12345.pdf              # Roll number as filename
│   ├── 12346.pdf
│   └── ...
├── CH3501/
│   ├── model_answer.pdf
│   ├── 12345.pdf
│   ├── 12346.pdf
│   └── ...
```

Config file example:
```json
{
  "max_marks": 100,
  "metadata": "Optional metadata for the batch"
}
```

## Key Requirements
1. **No inner functionality changes** - Keep all evaluation logic intact
2. **Data flow restructuring** - Pass course_code, model_answer, student_answers as parameters
3. **Max marks at root level** - Single max_marks value entered at root folder level, applied to all courses and evaluations
4. **Remove roles** - Eliminate teacher/student entities; use filename (roll number) as identifier for answer sheets
5. **Queue-based processing per course** - Create processing queue for each course
6. **Serial course processing** - Process courses sequentially initially
7. **Multithreading support** - Process multiple course codes in parallel

---

## Implementation Steps

### Step 1: Create Course Processing Manager
**File**: `utils/course_processor.py`

Create a new class to manage course-level operations with the following responsibilities:

**Initialization**: Accept root_directory as parameter and maintain internal dictionary to store discovered courses.

**discover_courses() method**: This is the core scanning method that should:
- Read and parse config.json from the root directory to extract max_marks value
- Validate that max_marks exists and is a valid number
- Scan all subdirectories in the root (ignoring config.json and non-directory items)
- For each subdirectory, extract and validate the course code (should match pattern like MB3103, CH3501)
- Within each course folder, locate the model_answer.pdf file
- Identify all student answer sheet PDFs (files with roll numbers as names, e.g., 12345.pdf, 12346.pdf)
- Organize this data into a structured format where each course contains:
  - Course code (folder name)
  - Full path to course folder
  - Path to model answer PDF
  - Max marks (from root config, same for all courses)
  - List of student sheets with their roll numbers and file paths
- Return both the organized courses data and the max_marks value

**get_course_queue() method**: Create a processing queue for a specific course code that organizes the tasks in sequence:
- First task: load and process the model answer (extract text, convert to images)
- Subsequent tasks: for each student sheet, evaluate against the model answer
- Queue should maintain order for sequential processing

### Step 2: Refactor Evaluation Pipeline
**File**: `utils/evaluation_pipeline.py`

Create a new evaluation pipeline class that wraps existing evaluation logic with course-level orchestration. The pipeline should:

**Method: evaluate_course()**
Accept the following parameters:
- `course_code` - String identifier for the course (e.g., "MB3103")
- `model_answer_data` - Dictionary containing path and metadata for model answer PDF
- `student_sheets` - List of dictionaries, each containing roll_number (filename identifier) and path to student answer PDF
- `max_marks` - Integer value from root config (NOT optional - this is mandatory)
- `question` - Optional parameter for course-specific questions

The method should:
1. Extract text from the model answer PDF using existing PDFProcessor.extract_text_from_pdf()
2. Convert model answer PDF to images using existing PDFProcessor.convert_pdf_to_images()
3. For each student sheet in the list:
   - Extract text from student PDF using existing PDFProcessor logic
   - Convert student PDF to images using existing PDFProcessor logic
   - Call existing gemini_service.evaluate_answer() method with:
     - Model answer text and images
     - Student answer text and images
     - The max_marks value passed from root config
     - Optional question parameter
4. Collect evaluation results for each student and package them with course_code and roll_number identifiers
5. Return the complete list of evaluation results

**Important**: Keep all existing evaluation business logic intact - this pipeline is only restructuring how data flows through the system and adding course/roll_number context to results.

### Step 3: Create Multithreading Manager
**File**: `utils/multithreading_manager.py`

Implement a multithreading manager class that handles both parallel and sequential processing of multiple courses.

**Initialization**: Accept max_workers parameter (default 3) to control thread pool size. Maintain internal dictionaries to track:
- Results for each course processed
- Status for each course (queued, processing, completed, failed)
- Thread executor for managing worker threads

**process_courses_parallel() method**: 
This method orchestrates parallel course processing:
- Accept courses_data dictionary and max_marks value as parameters
- Create thread pool with specified max_workers
- For each course in courses_data:
  - Mark status as "queued"
  - Submit course processing as separate task to thread pool
  - Store future object for tracking
- Wait for all futures to complete (with proper error handling)
- Update status for each course (completed or failed with error message)
- Log errors if courses fail
- Return aggregated results dictionary keyed by course_code

**_process_single_course() method**:
This internal method runs within a thread for each course:
- Accept course_code, course_info, and max_marks
- Update status to "processing"
- Call EvaluationPipeline.evaluate_course() with course data and max_marks
- Handle any exceptions and log them
- Return results

**process_courses_sequential() method**:
This method processes courses one after another (for testing/comparison):
- Accept courses_data and max_marks
- Loop through each course
- For each, update status to "processing"
- Call _process_single_course() directly (no threading)
- Update status to "completed" after processing
- Return aggregated results

**Thread Safety Considerations**:
- Use thread-safe data structures for results and status dictionaries
- Ensure database operations are thread-safe (PyMongo handles this)
- Each thread should work on isolated files to avoid conflicts

### Step 4: Create Course Processing Endpoint
**File**: Modify `app.py`

Add new endpoints for batch course processing:

**POST /api/batch/process-courses**
This endpoint handles the entire batch processing workflow:

*Request Parameters*:
- root_directory: Path to the root folder containing course subdirectories and config.json
- parallel: Boolean flag (default: true) to choose between parallel or sequential processing
- max_workers: Integer specifying number of concurrent threads (default: 3)

*Processing Flow*:
1. Validate root_directory exists and is accessible
2. Instantiate CourseProcessor with root directory
3. Call discover_courses() to scan for courses and retrieve max_marks from config.json
4. Validate that max_marks was successfully loaded
5. Instantiate MultithreadingManager with specified max_workers
6. Based on "parallel" flag, call either:
   - process_courses_parallel() for concurrent processing
   - process_courses_sequential() for serial processing
7. Upon completion, iterate through all results and store in database:
   - For each course and its evaluations:
     - Extract evaluation data (marks, grades, feedback, etc.)
     - Create database records using Evaluation.create() with:
       - course_code (course identifier)
       - roll_number (from filename)
       - model_answer content
       - student_answer content
       - max_marks (from root config)
       - All evaluation results and analysis
8. Return success response with:
   - Number of courses processed
   - Status of each course
   - Aggregated results
9. Handle and log any errors, returning appropriate error messages

**GET /api/batch/status**
Optional endpoint for monitoring ongoing batch processing:
- Track real-time status of all courses being processed
- Show which courses are queued, processing, completed, or failed
- Provide percentage completion
- Return current status without interfering with processing

### Step 5: Update Database Models
**File**: `models/evaluation.py`

Remove teacher/student roles, add `course_code` and `roll_number` fields:

Modify the Evaluation model's create() method to accept:
- course_code: Course identifier (e.g., "MB3103")
- roll_number: File name/roll number identifier (no longer using student_id or student_name)
- question: Optional question parameter
- model_answer: Full model answer text
- student_answer: Full student answer text
- extracted_text: Extracted/processed text from student answer
- max_marks: Maximum marks for this evaluation (from root config)
- evaluation_result: Dictionary containing AI evaluation analysis

*Database Record Structure*:
The create() method should build a document with:
- course_code: Direct course identifier
- roll_number: Student identifier (based on filename)
- All answer content (model and student)
- Max marks value
- Evaluation components extracted from evaluation_result:
  - marks_awarded: Numeric marks given
  - percentage: Percentage score
  - grade: Letter grade
  - strengths: List of strong points in answer
  - missing_points: List of missing concepts
  - feedback: Detailed feedback text
- Timestamps for creation and updates

Remove all references to:
- teacher_id
- student_id
- teacher_name
- student_name
- student_rollno (replace with roll_number from filename)

### Step 6: Add Root Config File Handler
**File**: `utils/config_loader.py`

Create utility to read root config.json:

```python
import json
import os

class ConfigLoader:
    @staticmethod
    def load_root_config(root_directory):
        """Load config.json from root directory"""
        config_path = os.path.join(root_directory, 'config.json')
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"config.json not found in {root_directory}")
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                max_marks = config.get('max_marks')
                
                if max_marks is None:
                    raise ValueError("max_marks not defined in config.json")
                
                return {
                    'max_marks': int(max_marks),
                    'metadata': config.get('metadata', {})
                }
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config.json: {str(e)}")
```

### Step 7: Configuration Updates
**File**: `config.py`

Add new configuration parameters:

```python
class Config:
    # ... existing config ...
    
    # Batch processing configuration
    BATCH_PROCESSING_MAX_WORKERS = int(os.getenv('BATCH_PROCESSING_MAX_WORKERS', '3'))
    BATCH_PROCESSING_TIMEOUT = int(os.getenv('BATCH_PROCESSING_TIMEOUT', '3600'))  # seconds
    SUPPORTED_COURSE_PATTERN = r'^[A-Z]{2}\d{4}$'  # e.g., MB3103
    CONFIG_FILE_NAME = 'config.json'  # Root level config file
```

---

## Data Flow Diagram

### Current Flow
```
PDF Upload → Extract Text/Images → Evaluate → Store Result
```

### New Flow (Per Course)
```
Root Directory
    ↓
Discover Courses (CourseProcessor)
    ↓
For Each Course:
    ├─ Load Model Answer
    └─ For Each Student Sheet:
        ├─ Extract Text/Images
        ├─ Evaluate (reuse existing logic)
        └─ Store with course_code
```

### Multithreading Flow
```
ThreadPool (3 workers)
    ├─ Thread 1: Process MB3103 (course queue)
    ├─ Thread 2: Process CH3501 (course queue)
    └─ Thread 3: Process NX2201 (course queue)
    
Result aggregation → Store all → Return status
```

---

## Testing Strategy

1. **Unit Tests**: Test CourseProcessor independently
   - Verify correct course discovery
   - Verify queue creation
   
2. **Integration Tests**: Test EvaluationPipeline
   - Ensure existing evaluation logic works with new parameters
   - Verify course_code is properly threaded through
   
3. **Load Tests**: MultiThreading Manager
   - Test with 1, 3, 5 courses
   - Compare time: serial vs parallel
   - Verify no data mixing between threads

4. **End-to-End Tests**: Full pipeline
   - Create test directory structure with multiple courses
   - Submit batch processing request
   - Verify all results stored correctly with course_codes

---

## Migration Checklist

- [ ] Create `utils/course_processor.py`
- [ ] Create `utils/evaluation_pipeline.py`
- [ ] Create `utils/multithreading_manager.py`
- [ ] Create `utils/config_loader.py`
- [ ] Add batch processing endpoints to `app.py`
- [ ] Update `models/evaluation.py` - remove teacher/student roles, add course_code and roll_number
- [ ] Update `config.py` with batch processing config
- [ ] Add thread-safety measures to database operations
- [ ] Create config.json template for users
- [ ] Create unit tests for new modules
- [ ] Create integration tests with sample course structure
- [ ] Update API documentation
- [ ] Add logging for thread execution tracking
- [ ] Document root directory structure requirements

---

## Thread Safety Considerations

1. **Database Operations**: Ensure MongoDB operations are thread-safe (they are by default with PyMongo)
2. **Shared Resources**: 
   - `gemini_service` - verify it handles concurrent API calls
   - File I/O - each thread should work on isolated files
3. **Result Aggregation**: Use thread-safe data structures (dict with locks if needed)

---

## Notes
- Keep all existing endpoints functional (backward compatibility)
- Preserve existing API contracts
- Only add new batch processing endpoints
- All inner business logic remains unchanged
- New modules are thin wrappers around existing functionality
- Max marks is centralized at root level (config.json) and applied to all courses/evaluations
- Student/teacher roles removed - all records identified by course_code and roll_number
- File naming convention: use roll numbers (e.g., 12345.pdf) for student answer sheets

## Sample Root Directory Structure

```
/batch_evaluation_2024/
├── config.json                    # Max marks defined here
├── MB3103/
│   ├── model_answer.pdf
│   ├── 12345.pdf                 # Roll number
│   ├── 12346.pdf
│   ├── 12347.pdf
│   └── ...
├── CH3501/
│   ├── model_answer.pdf
│   ├── 12345.pdf
│   ├── 12346.pdf
│   ├── 12348.pdf
│   └── ...
├── PH2401/
│   ├── model_answer.pdf
│   ├── 12345.pdf
│   ├── 12346.pdf
│   ├── 12349.pdf
│   └── ...
```

Sample config.json:
```json
{
  "max_marks": 100,
  "evaluation_date": "2024-04-02",
  "institution": "XYZ University"
}
```
