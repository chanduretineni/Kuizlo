# AI-Powered Text Editor Documentation

## Tech Stack

### Frontend
- **JavaScript Framework**: Next.js
- **Styling**: Tailwind CSS, ShadCN (for components), Material-UI
- **Text Editor**: TipTap
- **Icons**: Lucide React (for icons)


### Backend
- **Framework**: FastAPI 
- **Database**: MongoDB 
- **AI Integration**: OpenAI GPT API (for essay generation)
- **Background Tasks**: Celery with Redis or built in BackroundTasks
- **Authentication**: JSON Web Tokens (JWT)

### DevOps
- **Containerization**: Docker
- **Version Control**: Git + GitHub
- **CI/CD**: GitHub Actions

### Deployment
- **Database Hosting**: MongoDB Atlas

---

## Backend Endpoints Documentation

### 1. Reference Papers API
- **Endpoint**: `/get-references`
- **Method**: `POST`
- **Description**: Fetches 10-15 reference papers based on a given topic.
- **Request Body**:
  ```json
  {
    "topic": "machine learning in health care"
  }
- **Response**:
    ```json
    {
    "references": [
        {
        "id": "12345",
        "title": "Machine Learning Applications in Healthcare",
        "authors": ["John Doe", "Jane Smith"],
        "summary": "An overview of ML applications in healthcare.",
        "publication_date": "2023-04-15",
        "url": "https://example.com/paper1"
        },
        ...
    ]
    }

### 2.Generate Essay API
- **Endpoint**: `/generate-essay`
- **Method**: `POST`
- **Description**: Generates an essay using the ChatGPT API based on selected references.
- **Request Body**:
    ```json
    {
    "topic": "machine learning in health care",
    "selected_references": [
        {
        "id": "12345",
        "title": "Machine Learning Applications in Healthcare"
        },
        {
        "id": "12346",
        "title": "Deep Learning for Medical Imaging"
        }
    ]
    }
- **Response**:
    ```json
    {
    "essay": "Machine learning has transformed healthcare by enabling better diagnostics...",
    "citations": [
        {
        "reference_id": "12345",
        "citation": "Doe, J., & Smith, J. (2023). Machine Learning Applications in Healthcare. Retrieved from https://example.com/paper1"
        },
        {
        "reference_id": "12346",
        "citation": "Johnson, A., & Lee, B. (2023). Deep Learning for Medical Imaging. Retrieved from https://example.com/paper2"
        }
    ]
    }

### 3. Save Essay API
- **Endpoint**: `/save-essay`
- **Method**: `POST`
- **Description**: Saves the essay and citation data to the database.
- **Request Body**: 
    ```json
    {
    "user_id": "user123",
    "topic": "machine learning in health care",
    "essay": "Machine learning has transformed healthcare...",
    "citations": [
        {
        "reference_id": "12345",
        "citation": "Doe, J., & Smith, J. (2023). Machine Learning Applications in Healthcare. Retrieved from https://example.com/paper1"
        }
    ]
    }

- **Response**:
    ```json
    {
    "status": "success",
    "message": "Essay saved successfully"
    }

### 4. Retrieve Saved Essays API
- **Endpoint**: `/get-essays`
- **Method**: `GET`
- **Description**: Retrieves all saved essays for a specific user.
- **Query Parameters**:
    ```json
    {
    "user_id": "user123"
    }

- **Response**:
    ```json
    {
    "essays": [
        {
        "essay_id": "essay001",
        "topic": "machine learning in health care",
        "essay": "Machine learning has transformed healthcare...",
        "citations": [
            {
            "reference_id": "12345",
            "citation": "Doe, J., & Smith, J. (2023). Machine Learning Applications in Healthcare. Retrieved from https://example.com/paper1"
            }
        ]
        },
        {
        "essay_id": "essay002",
        "topic": "deep learning in healthcare",
        "essay": "Deep learning is a subset of machine learning...",
        "citations": [
            {
            "reference_id": "12346",
            "citation": "Johnson, A., & Lee, B. (2023). Deep Learning for Medical Imaging. Retrieved from https://example.com/paper2"
            }
        ]
        }
    ]
    }


# Frontend-Backend Integration Workflow

## 1. Topic Entry and Reference Display

### Workflow:
1. **User Action**:  
   The user enters a topic in the input field.
   
2. **Frontend Request**:  
   The frontend sends a `POST` request to the `/get-references` endpoint with the topic as payload.
   
3. **Backend Processing**:  
   The backend:
   - Fetches reference papers from a database or an external source.
   - Returns a list of references with summary details.
   
4. **Frontend Display**:  
   References are displayed in the left panel of the UI.

---

## 2. Reference Selection and Essay Generation

### Workflow:
1. **User Action**:  
   The user selects one or more references from the left panel.

2. **Frontend Request**:  
   The frontend sends a `POST` request to the `/generate-essay` endpoint with the selected references as payload.

3. **Backend Processing**:  
   The backend:
   - Uses the ChatGPT API to generate an essay based on the references and topic.
   - Formats the essay with proper citations and references.

4. **Frontend Display**:  
   The generated essay is displayed in the text editor.

---

## 3. Save Essay

### Workflow:
1. **User Action**:  
   The user clicks the "Save Essay" button after editing or reviewing the essay.

2. **Frontend Request**:  
   The frontend sends a `POST` request to the `/save-essay` endpoint with:
   - The essay text.
   - Citation data.

3. **Backend Processing**:  
   The backend:
   - Stores the essay and associated metadata in the MongoDB database.

---

## 4. Retrieve Saved Essays

### Workflow:
1. **User Action**:  
   The user navigates to the "Saved Essays" section in the application.

2. **Frontend Request**:  
   The frontend sends a `GET` request to the `/get-essays` endpoint with the user's ID as a query parameter.

3. **Backend Processing**:  
   The backend:
   - Retrieves saved essays associated with the user from MongoDB.
   - Returns the list of essays.

4. **Frontend Display**:  
   The saved essays are displayed for the user to view or edit.
