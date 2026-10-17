import sys
import os

# Add parent directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.database import SessionLocal, engine, Base
from models.hospital import (
    User, Department, Doctor, BlogPost, Comment, HospitalStat
)
from services.auth_service import AuthService


def seed_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if already seeded
        if db.query(Department).first():
            print("Database already contains data. Skipping initial seeding.")
            return

        print("Seeding initial database records...")

        # 1. Admin User
        admin_user = User(
            email="admin@mediplus.com",
            hashed_password=AuthService.get_password_hash("Admin123!"),
            full_name="Mediplus Administrator",
            phone="+1 235 2355 98",
            role="admin"
        )
        db.add(admin_user)

        # 2. Departments
        departments_data = [
            {"name": "Neurology", "slug": "neurology", "icon": "flaticon-stethoscope", "description": "Expert diagnosis and surgical management of neurological conditions and nervous system disorders.", "image_url": "assets/images/dept-1.jpg"},
            {"name": "Surgical", "slug": "surgical", "icon": "flaticon-stethoscope", "description": "Advanced surgical procedures with cutting-edge laparoscopic and minimally invasive technology.", "image_url": "assets/images/dept-2.jpg"},
            {"name": "Dental", "slug": "dental", "icon": "flaticon-stethoscope", "description": "Comprehensive dental healthcare including orthodontics, cosmetic oral surgery, and preventive care.", "image_url": "assets/images/dept-3.jpg"},
            {"name": "Ophthalmology", "slug": "ophthalmology", "icon": "flaticon-stethoscope", "description": "Complete eye care solutions from routine vision assessments to cataract and laser corrections.", "image_url": "assets/images/dept-1.jpg"},
            {"name": "Cardiology", "slug": "cardiology", "icon": "flaticon-stethoscope", "description": "Premier cardiovascular diagnostics, coronary care, and preventive heart wellness programs.", "image_url": "assets/images/dept-2.jpg"},
            {"name": "Traumatology", "slug": "traumatology", "icon": "flaticon-stethoscope", "description": "24/7 emergency trauma stabilization, acute wound surgery, and orthopedic rehabilitation.", "image_url": "assets/images/dept-3.jpg"},
            {"name": "Nuclear Magnetic", "slug": "nuclear-magnetic", "icon": "flaticon-stethoscope", "description": "Ultra high-resolution magnetic resonance imaging (MRI) and nuclear diagnostic imaging.", "image_url": "assets/images/dept-1.jpg"},
            {"name": "X-ray & Radiology", "slug": "x-ray", "icon": "flaticon-stethoscope", "description": "Rapid digital radiography, low-dose fluoroscopy, and 3D volumetric scanning.", "image_url": "assets/images/dept-2.jpg"},
            {"name": "Pediatrics", "slug": "pediatrics", "icon": "flaticon-stethoscope", "description": "Compassionate pediatric medicine dedicated to infant, child, and adolescent healthcare.", "image_url": "assets/images/dept-3.jpg"},
        ]

        created_depts = {}
        for d in departments_data:
            dept = Department(**d)
            db.add(dept)
            db.flush()
            created_depts[dept.slug] = dept

        # 3. Doctors
        doctors_data = [
            {
                "name": "Dr. Lloyd Wilson",
                "slug": "dr-lloyd-wilson",
                "department_id": created_depts["neurology"].id,
                "position": "Neurologist",
                "qualification": "MD, DM (Neurology)",
                "bio": "Senior Consultant Neurologist specializing in neuro-critical care and cognitive neurology.",
                "photo_url": "assets/images/doc-1.jpg",
                "phone": "+1 235 2355 98",
                "email": "dr.wilson@mediplus.com",
                "twitter": "https://twitter.com",
                "facebook": "https://facebook.com",
                "instagram": "https://instagram.com"
            },
            {
                "name": "Dr. Rachel Parker",
                "slug": "dr-rachel-parker",
                "department_id": created_depts["ophthalmology"].id,
                "position": "Ophthalmologist",
                "qualification": "MBBS, MS (Ophthalmology)",
                "bio": "Expert retinal specialist with over 15 years experience in corrective ophthalmic microsurgery.",
                "photo_url": "assets/images/doc-2.jpg",
                "phone": "+1 235 2355 99",
                "email": "dr.parker@mediplus.com",
                "twitter": "https://twitter.com",
                "facebook": "https://facebook.com",
                "instagram": "https://instagram.com"
            },
            {
                "name": "Dr. Ian Smith",
                "slug": "dr-ian-smith",
                "department_id": created_depts["dental"].id,
                "position": "Dentist",
                "qualification": "BDS, MDS (Prosthodontics)",
                "bio": "Dedicated oral surgeon focused on dental implants, smile design, and painless restorative dentistry.",
                "photo_url": "assets/images/doc-3.jpg",
                "phone": "+1 235 2355 90",
                "email": "dr.smith@mediplus.com",
                "twitter": "https://twitter.com",
                "facebook": "https://facebook.com",
                "instagram": "https://instagram.com"
            },
            {
                "name": "Dr. Alicia Henderson",
                "slug": "dr-alicia-henderson",
                "department_id": created_depts["pediatrics"].id,
                "position": "Pediatrician",
                "qualification": "MD (Pediatrics), FAAP",
                "bio": "Caring pediatrician committed to holistic child health development, vaccinations, and preventive wellness.",
                "photo_url": "assets/images/doc-4.jpg",
                "phone": "+1 235 2355 91",
                "email": "dr.henderson@mediplus.com",
                "twitter": "https://twitter.com",
                "facebook": "https://facebook.com",
                "instagram": "https://instagram.com"
            }
        ]

        for doc in doctors_data:
            db.add(Doctor(**doc))

        # 4. Hospital Stats
        stats_data = [
            {"key": "experience", "title": "Years of Experience", "number_value": 30, "suffix": "+", "icon": "flaticon-stethoscope"},
            {"key": "happy_patients", "title": "Happy Patients", "number_value": 4500, "suffix": "+", "icon": "flaticon-ambulance"},
            {"key": "doctors_count", "title": "Number of Doctors", "number_value": 84, "suffix": "", "icon": "flaticon-doctor"},
            {"key": "staff_count", "title": "Number of Staffs", "number_value": 300, "suffix": "+", "icon": "flaticon-24-hours"}
        ]
        for s in stats_data:
            db.add(HospitalStat(**s))

        # 5. Blog Articles
        blogs_data = [
            {
                "title": "Scary Thing That You Don't Get Enough Sleep",
                "slug": "scary-thing-not-enough-sleep",
                "excerpt": "Far far away, behind the word mountains, far from the countries Vokalia and Consonantia, there live the blind texts.",
                "content": "Adequate sleep is as vital to good health as diet and exercise. Good sleep improves brain performance, mood, and health. Not getting enough quality sleep regularly raises the risk of many diseases and disorders. These range from heart disease and stroke to obesity and dementia.",
                "image_url": "assets/images/image_1.jpg",
                "author_name": "Admin",
                "category": "Neurology"
            },
            {
                "title": "Healthy Food For A Stronger Immune System",
                "slug": "healthy-food-stronger-immune-system",
                "excerpt": "Nutritious diets packed with vital vitamins, zinc, and antioxidants help protect against seasonal illnesses and fatigue.",
                "content": "Eating a healthy, balanced diet plays an essential role in staying well. Consuming immune-strengthening foods like citrus fruits, broccoli, garlic, ginger, spinach, and almonds ensures your natural defenses stay resilient.",
                "image_url": "assets/images/image_2.jpg",
                "author_name": "Admin",
                "category": "Cardiology"
            },
            {
                "title": "Modern Advances In Minimally Invasive Surgery",
                "slug": "modern-advances-minimally-invasive-surgery",
                "excerpt": "Revolutionary laparoscopic techniques reduce patient recovery times and minimize surgical trauma.",
                "content": "Minimally invasive surgery allows doctors to use a variety of techniques that cause less damage to the body than open surgery. In general, minimally invasive surgery is associated with less pain, shorter hospital stays, and fewer complications.",
                "image_url": "assets/images/image_3.jpg",
                "author_name": "Admin",
                "category": "Surgical"
            },
            {
                "title": "How Daily Exercise Protects Cardiovascular Health",
                "slug": "daily-exercise-cardiovascular-health",
                "excerpt": "Regular aerobic activity strengthens heart muscle fibers and regulates resting arterial blood pressure.",
                "content": "Physical activity improves blood circulation, lowers triglycerides, elevates HDL cholesterol, and manages insulin levels effectively.",
                "image_url": "assets/images/image_4.jpg",
                "author_name": "Admin",
                "category": "Cardiology"
            },
            {
                "title": "Essential Dental Care Tips For Lifelong Healthy Smiles",
                "slug": "essential-dental-care-tips",
                "excerpt": "Proper brushing, interdental flossing, and periodic prophylaxis prevent periodontal complications.",
                "content": "Good dental and oral hygiene helps prevent bad breath, tooth decay, and gum disease—and can help you keep your teeth as you get older.",
                "image_url": "assets/images/image_5.jpg",
                "author_name": "Admin",
                "category": "Dental"
            },
            {
                "title": "Recognizing Early Signs of Vision Impairment",
                "slug": "recognizing-early-vision-impairment",
                "excerpt": "Regular retinal examinations can diagnose asymptomatic eye conditions before irreparable loss occurs.",
                "content": "Periodic eye exams ensure proactive tracking of intraocular pressure and visual acuity, keeping your eyesight crisp and healthy.",
                "image_url": "assets/images/image_6.jpg",
                "author_name": "Admin",
                "category": "Ophthalmology"
            }
        ]

        for b_data in blogs_data:
            blog = BlogPost(**b_data)
            db.add(blog)
            db.flush()

            # Add demo comment
            comment = Comment(
                blog_id=blog.id,
                name="John Doe",
                email="john.doe@example.com",
                website="https://johndoe.me",
                message="Very informative article! Thank you for sharing such critical healthcare insights."
            )
            db.add(comment)

        db.commit()
        print("Initial database seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()

