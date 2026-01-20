"""
Seed script for development data.
"""
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db import models

def seed_data():
    """Add seed data."""
    db: Session = SessionLocal()
    try:
        # Create a sample person
        person = db.query(models.PersonProfile).filter(
            models.PersonProfile.name == "Test Person"
        ).first()
        
        if not person:
            person = models.PersonProfile(
                name="Test Person",
                consent_confirmed=True,
                subject_is_adult=True
            )
            db.add(person)
            db.commit()
            db.refresh(person)
            print(f"Created test person: {person.id}")
        else:
            print(f"Test person already exists: {person.id}")
    
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
