-- Initialize the AI Receptionist Database
-- This runs automatically when the PostgreSQL container starts

-- Enable pgvector extension for face embedding storage
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create enum types
CREATE TYPE consent_status AS ENUM ('pending', 'granted', 'denied', 'revoked');
CREATE TYPE visit_status AS ENUM ('arrived', 'in_meeting', 'departed', 'cancelled');
CREATE TYPE employee_availability AS ENUM ('available', 'busy', 'away', 'offline');

-- Persons table: stores all recognized visitors
CREATE TABLE IF NOT EXISTS persons (
    person_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    company VARCHAR(255),
    role VARCHAR(255),
    image_path VARCHAR(512),
    face_embedding vector(512),
    consent_status consent_status DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen TIMESTAMP WITH TIME ZONE,
    visit_count INTEGER DEFAULT 0
);

-- Employees table: internal office employees
CREATE TABLE IF NOT EXISTS employees (
    employee_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(50),
    department VARCHAR(255),
    designation VARCHAR(255),
    office_location VARCHAR(255),
    availability employee_availability DEFAULT 'available',
    face_embedding vector(512),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Visits table: tracks each visit instance
CREATE TABLE IF NOT EXISTS visits (
    visit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id UUID REFERENCES persons(person_id) ON DELETE CASCADE,
    employee_to_meet UUID REFERENCES employees(employee_id),
    arrival_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    departure_time TIMESTAMP WITH TIME ZONE,
    purpose TEXT,
    status visit_status DEFAULT 'arrived',
    conversation_id UUID,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Conversations table: stores conversation sessions
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id UUID REFERENCES persons(person_id) ON DELETE SET NULL,
    session_id VARCHAR(255) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    summary TEXT,
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Conversation messages table: individual messages in a conversation
CREATE TABLE IF NOT EXISTS conversation_messages (
    message_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(name);
CREATE INDEX IF NOT EXISTS idx_persons_last_seen ON persons(last_seen);
CREATE INDEX IF NOT EXISTS idx_visits_person_id ON visits(person_id);
CREATE INDEX IF NOT EXISTS idx_visits_arrival ON visits(arrival_time);
CREATE INDEX IF NOT EXISTS idx_conversations_person ON conversations(person_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON conversation_messages(conversation_id);

-- Create vector similarity index for face matching
CREATE INDEX IF NOT EXISTS idx_persons_face_embedding ON persons
    USING ivfflat (face_embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_employees_face_embedding ON employees
    USING ivfflat (face_embedding vector_cosine_ops) WITH (lists = 100);

-- Insert sample employees
INSERT INTO employees (name, email, phone, department, designation, office_location, availability) VALUES
    ('Mr. Sharma', 'sharma@codeorigin.ai', '+91-9876543210', 'Management', 'Director', 'Room 101', 'available'),
    ('Priya Patel', 'priya@codeorigin.ai', '+91-9876543211', 'Engineering', 'Tech Lead', 'Room 205', 'available'),
    ('Arun Kumar', 'arun@codeorigin.ai', '+91-9876543212', 'Engineering', 'Senior Developer', 'Room 206', 'available'),
    ('Sneha Gupta', 'sneha@codeorigin.ai', '+91-9876543213', 'HR', 'HR Manager', 'Room 103', 'available'),
    ('Rajesh Mehta', 'rajesh@codeorigin.ai', '+91-9876543214', 'Sales', 'Sales Director', 'Room 301', 'available')
ON CONFLICT DO NOTHING;
