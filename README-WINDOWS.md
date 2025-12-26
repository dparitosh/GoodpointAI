# GraphTrace - Windows Setup Guide

This guide provides instructions for running GraphTrace on Windows using PowerShell or Command Prompt.

## Prerequisites

### Required Software
1. **Python 3.8+** - [Download](https://www.python.org/downloads/)
   - During installation, check "Add Python to PATH"
   - Verify: `python --version`

2. **Node.js 16+** - [Download](https://nodejs.org/)
   - npm is included with Node.js
   - Verify: `node --version` and `npm --version`

3. **Git** (optional) - [Download](https://git-scm.com/download/win)

### Neo4j Database
You need access to a Neo4j database. Options:
- **Neo4j AuraDB** (Cloud) - [Free tier available](https://neo4j.com/cloud/aura/)
- **Local Neo4j Desktop** - [Download](https://neo4j.com/download/)

## Environment Configuration

### Backend Configuration
1. Navigate to `python_backend` folder
2. Create a `.env` file with your Neo4j credentials:
```env
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

### Frontend Configuration
1. Navigate to `e2etraceapp` folder
2. Create or update `.env` file:
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_NEO4J_URI=bolt://localhost:7687
VITE_NEO4J_USER=neo4j
```

## Running the Application

### Option 1: Start All Services (Recommended)

**Using PowerShell:**
```powershell
.\start-all.ps1
```

**Using Command Prompt:**
```cmd
start-all.bat
```

This will open two separate windows for backend and frontend services.

### Option 2: Start Services Individually

#### Backend Only

**PowerShell:**
```powershell
.\start-backend.ps1
```

**Command Prompt:**
```cmd
start-backend.bat
```

The backend will be available at:
- API: `http://localhost:8000`
- Interactive API Docs: `http://localhost:8000/docs`

#### Frontend Only

**PowerShell:**
```powershell
.\start-frontend.ps1
```

**Command Prompt:**
```cmd
start-frontend.bat
```

The frontend will be available at:
- Application: `http://localhost:5173`

## Quick Smoke Test (Windows)

If you see `>>>` in your terminal, you're inside the Python REPL — exit with `exit()` before running PowerShell commands.

From PowerShell, you can run a backend smoke test (health + workflow start) like this:

```powershell
cd .\python_backend
.\smoke-backend.ps1
```

Optional parameters:

```powershell
.\smoke-backend.ps1 -BaseUrl http://127.0.0.1:8000 -WorkflowId wf_demo_001 -TimeoutSec 10
```

## Script Features

### Automated Setup
All scripts automatically:
- ✓ Check for required software (Python/Node.js)
- ✓ Create Python virtual environment (backend)
- ✓ Install/update dependencies
- ✓ Create default `.env` files if missing
- ✓ Start development servers with hot reload

### Virtual Environment
The backend scripts create and use a Python virtual environment (`venv`) to isolate dependencies. This is created automatically on first run.

## Building for Production

### Build Frontend
```cmd
cd e2etraceapp
npm run build
```

The production build will be in `e2etraceapp/dist/`

### Run Backend in Production Mode
```cmd
cd python_backend
venv\Scripts\activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## Troubleshooting

### PowerShell Execution Policy Error
If you get an execution policy error when running `.ps1` scripts:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Python Not Found
- Ensure Python is installed and added to PATH
- Try using `py` instead of `python` command
- Reinstall Python and check "Add to PATH" during installation

### Port Already in Use
If ports 8000 or 5173 are already in use:
- Close other applications using these ports
- Or modify the port in the respective scripts

### Module Import Errors (Backend)
```cmd
cd python_backend
venv\Scripts\activate
pip install -r requirement.txt
```

### Dependencies Issues (Frontend)
```cmd
cd e2etraceapp
rmdir /s /q node_modules
npm install
```

## Additional Commands

### Backend Commands
```cmd
cd python_backend

# Activate virtual environment
venv\Scripts\activate

# Run tests
python -m pytest tests/ -v

# Install specific package
pip install package-name

# Update all dependencies
pip install -r requirement.txt --upgrade
```

### Frontend Commands
```cmd
cd e2etraceapp

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run linter
npm run lint
```

## File Structure
```
graphTrace/
├── start-all.ps1          # PowerShell - Start all services
├── start-all.bat          # Batch - Start all services
├── start-backend.ps1      # PowerShell - Start backend only
├── start-backend.bat      # Batch - Start backend only
├── start-frontend.ps1     # PowerShell - Start frontend only
├── start-frontend.bat     # Batch - Start frontend only
├── python_backend/        # Backend source code
│   ├── .env              # Backend environment variables
│   ├── venv/             # Python virtual environment (auto-created)
│   └── requirement.txt   # Python dependencies
└── e2etraceapp/          # Frontend source code
    ├── .env              # Frontend environment variables
    └── package.json      # Node dependencies
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify all prerequisites are installed correctly
3. Ensure `.env` files are configured with valid credentials
4. Check console output for specific error messages

## Development Mode Features

Both frontend and backend run in development mode with:
- **Hot Reload**: Changes are automatically detected and applied
- **Error Display**: Detailed error messages in browser/console
- **Debug Mode**: Additional logging and debugging features

To stop the servers, press `Ctrl+C` in the respective terminal windows.
