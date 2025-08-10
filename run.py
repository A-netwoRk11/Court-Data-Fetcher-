
"""
Setup and run script for Court Data Fetcher
"""

import os
import sys
import subprocess
import platform

def check_python_version():
    """Check if Python 3.12 is being used"""
    major, minor = sys.version_info[:2]
    if major != 3 or minor != 12:
        print(f"❌ Warning: This application requires Python 3.12")
        print(f"   You are using Python {major}.{minor}")
        print(f"   Some features may not work as expected.")
        
        
        response = input("Do you want to continue anyway? (y/n): ").lower()
        if response != 'y':
            sys.exit(1)
    else:
        print("✅ Python 3.12 detected")
        
def install_dependencies():
    """Install Python dependencies"""
    print("Installing Python dependencies...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing dependencies: {e}")
        return False

def setup_environment():
    """Setup environment variables"""
    if not os.path.exists('.env'):
        print("Creating .env file from template...")
        try:
            import shutil
            shutil.copy('.env.example', '.env')
            print("✅ .env file created. Please review and update the configuration.")
        except Exception as e:
            print(f"❌ Error creating .env file: {e}")
            return False
    else:
        print("✅ .env file already exists.")
    
    return True

def initialize_database():
    """Initialize the database"""
    print("Initializing database...")
    try:
        subprocess.check_call([sys.executable, 'init_db.py'])
        print("✅ Database initialized successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error initializing database: {e}")
        return False

def run_tests():
    """Run tests"""
    print("Running tests...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pytest', 'tests/', '-v'])
        print("✅ All tests passed!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Some tests failed: {e}")
        return False

def run_application():
    """Run the Flask application"""
    print("Starting Court Data Fetcher application...")
    print("🌐 Application will be available at: http://localhost:5000")
    print("📊 Statistics page: http://localhost:5000/stats")
    print("🔗 API endpoint example: http://localhost:5000/api/case/1234")
    print("\nPress Ctrl+C to stop the application")
    
    try:
        subprocess.check_call([sys.executable, 'app.py'])
    except KeyboardInterrupt:
        print("\n✅ Application stopped.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running application: {e}")

def main():
    """Main setup and run function"""
    print("=" * 60)
    print("🏛️  Court Data Fetcher - Setup and Run")
    print("=" * 60)
    
    
    check_python_version()
    
    
    steps = [
        ("Installing dependencies", install_dependencies),
        ("Setting up environment", setup_environment),
        ("Initializing database", initialize_database),
    ]
    
    for step_name, step_func in steps:
        print(f"\n📋 {step_name}...")
        if not step_func():
            print(f"❌ Setup failed at: {step_name}")
            sys.exit(1)
    
    
    print("\n🧪 Would you like to run tests? (y/n): ", end="")
    if input().lower().strip() in ['y', 'yes']:
        run_tests()
    
    
    print("\n🚀 Would you like to start the application now? (y/n): ", end="")
    if input().lower().strip() in ['y', 'yes']:
        run_application()
    else:
        print("\n✅ Setup complete!")
        print("\nTo start the application later, run:")
        print("  python app.py")
        print("\nOr use the development server:")
        print("  flask run --debug")

if __name__ == '__main__':
    main()
