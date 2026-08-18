# 🤖 AI Avatar Receptionist

> **Intelligent AI-powered office receptionist for Code Origin.AI**

An end-to-end AI receptionist system that uses computer vision (YOLO + InsightFace), AWS Bedrock Llama 3 70B for natural conversation, Amazon Polly for text-to-speech, and a realistic animated avatar — all orchestrated through a state machine that handles new visitors, returning visitors, and real-time voice conversations.

---

## 🎯 What This System Does

When somebody walks into your office:

1. **Camera detects a person** (not a chair, bag, or laptop) using YOLO
2. **Face detection** identifies if a face is visible (InsightFace/RetinaFace)
3. **Face recognition** searches the face against your database using vector similarity (pgvector)
4. Based on the match result:
   - **New person** → Avatar greets them, asks their name, requests consent to remember them
   - **Returning person** → Avatar greets them by name: *"Hi, Rahul! Welcome back."*
5. **Real-time voice conversation** powered by Llama 3 70B
6. **Text-to-Speech** converts responses to natural audio (Amazon Polly)
7. **Animated avatar** speaks with lip sync to the visitor

---

## 🏗️ Architecture

```
                    OFFICE
                      │
              Camera + Microphone
                      │
                      ▼
              AI Avatar Display
                      │
              WebSocket (Real-time)
                      │
                      ▼
               ┌─────────────────────────┐
               │    FastAPI Backend       │
               │                         │
               │  ┌──────┐  ┌────────┐  │
               │  │Vision│  │  Voice  │  │
               │  │YOLO  │  │STT/TTS │  │
               │  │Face  │  │  VAD   │  │
               │  └──┬───┘  └────┬───┘  │
               │     │           │       │
               │  ┌──▼───────────▼──┐   │
               │  │ Conversation    │   │
               │  │    Manager      │   │
               │  │ (State Machine) │   │
               │  └────────┬────────┘   │
               │           │            │
               │  ┌────────▼────────┐   │
               │  │  AWS Bedrock    │   │
               │  │ Llama 3 70B    │   │
               │  └────────┬────────┘   │
               │           │            │
               │  ┌────────▼────────┐   │
               │  │  PostgreSQL     │   │
               │  │  + pgvector     │   │
               │  └─────────────────┘   │
               └─────────────────────────┘
```

### State Machine Flow

```
                 CAMERA FRAME
                      │
               Person detected?
                  /       \
                NO         YES
                ↓           ↓
            (idle)     Face detected?
                         /    \
                       NO      YES
                       ↓        ↓
                   (wait)    Vector Search
                               ↓
                       ┌───────┴───────┐
                       ↓               ↓
                    MATCH           NO MATCH
                       ↓               ↓
                 Known Person      New Person
                       ↓               ↓
               "Hi Rahul!"     "Welcome! Your name?"
                       ↓               ↓
                       └──────┬────────┘
                              ↓
                    Voice Conversation Loop
                              ↓
                    Llama 3 → TTS → Avatar
```

---

## 📁 Project Structure

```
AI-AVATAR-RECEPTIONIST/
│
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Configuration (Pydantic Settings)
│   │
│   ├── api/
│   │   ├── visitor.py            # Visitor CRUD, consent, visits
│   │   ├── conversation.py       # Conversation start/message/end
│   │   ├── employee.py           # Employee directory
│   │   ├── dashboard.py          # Dashboard stats & status
│   │   └── websocket.py          # Real-time WebSocket
│   │
│   ├── ai/
│   │   ├── bedrock.py            # AWS Bedrock Llama client
│   │   ├── prompts.py            # System prompts & context builder
│   │   └── conversation_manager.py # State machine orchestrator
│   │
│   ├── vision/
│   │   ├── person_detection.py   # YOLO person detector
│   │   ├── face_detection.py     # InsightFace face detector
│   │   ├── face_embedding.py     # 512-dim face embeddings
│   │   ├── face_matching.py      # pgvector similarity search
│   │   ├── camera.py             # Camera capture service
│   │   └── pipeline.py           # Vision pipeline orchestrator
│   │
│   ├── voice/
│   │   ├── speech_to_text.py     # AWS Transcribe STT
│   │   ├── text_to_speech.py     # Amazon Polly TTS
│   │   └── vad.py                # WebRTC Voice Activity Detection
│   │
│   ├── database/
│   │   ├── database.py           # Async SQLAlchemy engine
│   │   ├── models.py             # ORM models
│   │   ├── visitors.py           # Visitor repository
│   │   └── init.sql              # DB initialization script
│   │
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx               # Main app with routing
│   │   ├── main.tsx              # Entry point
│   │   ├── index.css             # TailwindCSS + animations
│   │   │
│   │   ├── pages/
│   │   │   ├── ReceptionistPage.tsx  # Main receptionist UI
│   │   │   └── DashboardPage.tsx     # Management dashboard
│   │   │
│   │   ├── components/
│   │   │   ├── Avatar.tsx        # Animated AI avatar
│   │   │   ├── CameraFeed.tsx    # Camera with detection
│   │   │   ├── ConversationPanel.tsx  # Chat interface
│   │   │   └── Navbar.tsx        # Navigation
│   │   │
│   │   └── hooks/
│   │       ├── useWebSocket.ts   # WebSocket connection
│   │       ├── useSpeechRecognition.ts  # Browser STT
│   │       └── useCamera.ts      # getUserMedia + capture
│   │
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── Dockerfile
│
├── docker-compose.yml
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

- **Docker & Docker Compose** (recommended for easiest setup)
- **Python 3.11+** (for local backend development)
- **Node.js 18+** (for local frontend development)
- **AWS Account** with Bedrock access enabled for `ap-south-1`
- **Webcam** (for real-time person detection)

### 1. Clone & Configure

```bash
# Clone the repository
git clone https://github.com/bhumikacodeoriginai-hub/RelasticAiavatrar.git
cd RelasticAiavatrar

# Copy the environment file
cp .env.example .env

# Edit .env with your AWS credentials
nano .env
```

### 2. Set Your AWS Credentials

In your `.env` file, set these critical values:

```env
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=your_actual_access_key
AWS_SECRET_ACCESS_KEY=your_actual_secret_key
BEDROCK_MODEL_ID=meta.llama3-70b-instruct-v1:0
```

### 3. Start with Docker (Recommended)

```bash
# Start all services (PostgreSQL, Redis, Backend, Frontend)
docker-compose up -d

# Check logs
docker-compose logs -f backend

# Access the app
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### 4. Manual Setup (Without Docker)

#### Backend:

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL with pgvector (required)
# Option A: Use Docker just for the database
docker run -d --name ai_db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=ai_receptionist \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# Run database initialization
psql -h localhost -U postgres -d ai_receptionist -f database/init.sql

# Start Redis
docker run -d --name ai_redis -p 6379:6379 redis:7-alpine

# Download YOLO model (auto-downloads on first run)
# Download InsightFace model (auto-downloads on first run)

# Start the backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend:

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

---

## 🔑 AWS Configuration

### Required AWS Services

| Service | Purpose | Region |
|---------|---------|--------|
| **Bedrock** (Llama 3 70B) | AI conversation brain | ap-south-1 |
| **Polly** | Text-to-Speech (voice output) | ap-south-1 |
| **Transcribe** | Speech-to-Text (voice input) | ap-south-1 |

### Enable Bedrock Model Access

1. Go to AWS Console → Amazon Bedrock → Model access
2. Request access to `Meta Llama 3 70B Instruct`
3. Wait for approval (usually instant for Llama models)

### IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:ap-south-1::foundation-model/meta.llama3-70b-instruct-v1:0"
    },
    {
      "Effect": "Allow",
      "Action": [
        "polly:SynthesizeSpeech"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "transcribe:StartStreamTranscription"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## 📡 API Reference

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health check |
| `POST` | `/api/conversation/start` | Start new conversation |
| `POST` | `/api/conversation/message` | Send user message |
| `POST` | `/api/conversation/end/{id}` | End conversation |
| `GET` | `/api/visitors/` | List all visitors |
| `POST` | `/api/visitors/register` | Register new visitor |
| `PUT` | `/api/visitors/{id}/consent` | Update consent |
| `DELETE` | `/api/visitors/{id}` | Delete visitor (GDPR) |
| `GET` | `/api/employees/` | List employees |
| `GET` | `/api/dashboard/stats` | Dashboard statistics |

### WebSocket Endpoints

| Endpoint | Purpose |
|----------|---------|
| `ws://host/ws/conversation/{id}` | Real-time conversation |
| `ws://host/ws/dashboard` | Dashboard updates |

### WebSocket Protocol

**Client → Server:**
```json
{"type": "speech", "text": "Hello", "is_final": true}
{"type": "frame", "data": "<base64 image>"}
{"type": "start_session", "match_status": "no_match"}
{"type": "end_session", "session_id": "..."}
```

**Server → Client:**
```json
{"type": "response", "text": "Welcome!", "audio": "<base64>", "speech_marks": [...]}
{"type": "detection", "person_detected": true, "face_detected": true}
{"type": "state", "state": "active_conversation"}
```

---

## 🧠 How Each Component Works

### 1. Person Detection (YOLO)
- Uses YOLOv8 nano model for fast CPU inference
- Only detects class `person` (class ID 0), ignoring chairs/bags/laptops
- Sorts by bounding box area (closest person = largest box)

### 2. Face Detection (InsightFace/RetinaFace)
- Runs InsightFace within the detected person's bounding box
- Extracts facial landmarks (5 keypoints)
- Provides face quality/confidence scores

### 3. Face Embedding (ArcFace)
- Generates 512-dimensional normalized embeddings
- L2-normalized for cosine similarity comparison
- Stored in PostgreSQL using pgvector extension

### 4. Face Matching (pgvector)
- Uses cosine distance operator `<=>` for similarity search
- Threshold: 0.6 (configurable)
- IVFFlat index for fast approximate nearest neighbor search

### 5. Conversation Engine (Llama 3 70B)
- State machine manages conversation flow
- System prompt injected with visitor context
- Llama decides what to say; backend decides what's allowed
- Never gives Llama direct database/system access

### 6. Text-to-Speech (Amazon Polly)
- Neural engine with Indian English voice
- Returns speech marks (visemes) for lip sync
- SSML support for natural pauses and emphasis

### 7. Voice Activity Detection (WebRTC VAD)
- Detects speech start/end in real-time
- Configurable silence threshold (1.5s default)
- Minimum speech duration filter (300ms)

---

## 🗄️ Database Schema

```sql
-- Persons (visitors)
persons: person_id, name, email, phone, company, role,
         image_path, face_embedding(512), consent_status,
         last_seen, visit_count

-- Employees
employees: employee_id, name, email, department, designation,
           availability, face_embedding(512)

-- Visits
visits: visit_id, person_id, employee_to_meet,
        arrival_time, departure_time, purpose, status

-- Conversations
conversations: conversation_id, person_id, session_id,
               started_at, ended_at, summary

-- Messages
conversation_messages: message_id, conversation_id,
                       role, content, timestamp
```

---

## 🔒 Privacy & Security

This system handles biometric data (face embeddings). Key protections:

1. **Consent-based registration** — Faces are only stored after explicit permission
2. **Right to be forgotten** — `DELETE /api/visitors/{id}` removes all data
3. **Consent revocation** — Removes face embedding but keeps visit history
4. **No raw face storage** — Only 512-dim vectors stored, not images
5. **Backend authorization** — Llama cannot access database directly
6. **Credential protection** — System prompt instructs AI to never reveal credentials

---

## 🛠️ Development

### Environment Variables

See `.env.example` for all available configuration options. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `FACE_SIMILARITY_THRESHOLD` | 0.6 | Min cosine similarity for match |
| `BEDROCK_TEMPERATURE` | 0.5 | Llama response randomness |
| `BEDROCK_MAX_TOKENS` | 512 | Max response length |
| `POLLY_VOICE_ID` | Aditi | Amazon Polly voice |
| `CAMERA_INDEX` | 0 | Default camera device |

### Testing Without AWS

The system starts even if AWS credentials are invalid — services will retry on use. You can:
1. Test the frontend/WebSocket flow with the "Simulate" buttons
2. Test face detection locally with just the YOLO + InsightFace models
3. Mock the Bedrock responses for UI testing

### Development Phases (Recommended Order)

1. ✅ Camera → person detection → face detection
2. ✅ Face recognition → new/known person database
3. ✅ Speech-to-text → Llama → text response
4. ✅ Text-to-speech → speaker/audio
5. ✅ Avatar animation + lip sync
6. ✅ Full pipeline integration
7. Office receptionist functions (appointments, directory)
8. AWS deployment, security hardening, monitoring

---

## 🖥️ Deployment

### AWS EC2 (Recommended for first deployment)

```bash
# Use a GPU instance for faster inference (optional)
# t3.xlarge minimum for CPU-only

# SSH into your EC2 instance
ssh -i key.pem ec2-user@your-instance

# Install Docker
sudo yum install docker docker-compose -y
sudo systemctl start docker

# Clone and deploy
git clone <your-repo>
cd RelasticAiavatrar
cp .env.example .env
# Edit .env with production values
docker-compose up -d
```

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| Storage | 20 GB | 50 GB |
| GPU | Not required | NVIDIA T4 (faster face detection) |
| Camera | 720p USB | 1080p IP Camera |

---

## 📋 Modes of Operation

| Mode | Description |
|------|-------------|
| **Receptionist** | Welcome visitors, register new ones, greet returning |
| **Client** | Recognize clients, check appointments, notify employees |
| **Employee** | Greet employees by name briefly |
| **Security** | Flag unknown persons, escalate to human reception |
| **Dashboard** | Monitor visitors, stats, system health |

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is proprietary to Code Origin.AI.

---

## 🙏 Acknowledgments

- **YOLO** (Ultralytics) for real-time person detection
- **InsightFace** for face detection and embedding
- **AWS Bedrock** (Meta Llama 3 70B) for conversational AI
- **Amazon Polly** for natural text-to-speech
- **pgvector** for efficient vector similarity search
- **FastAPI** for high-performance async backend
- **React + Vite** for modern frontend
