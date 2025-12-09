# GraphTrace - Quick Reference

## 🚀 Quick Start (3 commands)
```bash
./diagnostics.sh    # 1. Check system
./install.sh        # 2. Install dependencies  
./start-all.sh      # 3. Start services
```

Then open: http://localhost:5173

## 📋 Available Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `diagnostics.sh` | Validate system | `./diagnostics.sh` |
| `install.sh` | Install all deps | `./install.sh` |
| `start-all.sh` | Start services | `./start-all.sh` |
| `stop-all.sh` | Stop services | `./stop-all.sh` |

## 🔧 Individual Service Control

### Backend Only
```bash
cd python_backend
source venv/bin/activate
python main.py
```

### Frontend Only
```bash
cd e2etraceapp
npm run dev
```

## 📊 Access Points

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Redoc | http://localhost:8000/redoc |

## 📝 Configuration Files

| File | Purpose |
|------|---------|
| `python_backend/.env` | Backend config (Neo4j) |
| `e2etraceapp/.env` | Frontend config (optional) |

## 🐛 Quick Troubleshooting

### Port Already in Use
```bash
# Kill process on port 8000
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9

# Kill process on port 5173  
lsof -i :5173 | grep LISTEN | awk '{print $2}' | xargs kill -9
```

### Backend Won't Start
```bash
# Check Neo4j credentials
cat python_backend/.env

# Reinstall dependencies
cd python_backend
pip install -r requirement.txt
```

### Frontend Won't Start
```bash
# Clean install
cd e2etraceapp
rm -rf node_modules package-lock.json
npm install
```

## 📁 Project Structure
```
graphTrace/
├── python_backend/      # FastAPI backend
├── e2etraceapp/         # React frontend
├── logs/                # Application logs
├── diagnostics.sh       # System check
├── install.sh           # Installation
├── start-all.sh         # Start services
└── stop-all.sh          # Stop services
```

## 🔍 View Logs
```bash
# Backend
tail -f logs/backend.log

# Frontend
tail -f logs/frontend.log
```

## 📖 Full Documentation
- Installation Guide: `INSTALLATION.md`
- Validation Report: `INSTALLATION_VALIDATION_REPORT.md`
- Bug Analysis: `BUGS_ANALYSIS_REPORT.md`

## ⚡ Development Workflow
```bash
# 1. Make changes to code
# 2. Services auto-reload (HMR/--reload enabled)
# 3. View logs for errors
# 4. Test in browser

# To restart services:
./stop-all.sh
./start-all.sh
```

## 🧪 Testing
```bash
# Backend tests
cd python_backend && pytest

# Frontend tests  
cd e2etraceapp && npm test
```

## 🛑 Stop Everything
```bash
./stop-all.sh
# OR manually:
pkill -f "python.*main.py"
pkill -f "vite"
```

## ✅ Health Check
```bash
# Backend alive?
curl http://localhost:8000/docs

# Frontend alive?
curl http://localhost:5173
```

## 🔐 Required Environment Variables

### Backend `.env`
```env
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

## 💡 Pro Tips
1. Always run `diagnostics.sh` before starting
2. Check logs first when debugging
3. Use `./stop-all.sh` before system shutdown
4. Keep .env files secure (never commit!)
5. Run `install.sh` after pulling new changes

## 🆘 Help
1. Run diagnostics: `./diagnostics.sh`
2. Check logs: `tail -f logs/*.log`  
3. Read docs: `INSTALLATION.md`
4. Review common issues in docs
