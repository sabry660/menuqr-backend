# 🚀 MenuQR Backend - Quick Start Guide (Neon + Render)

## 📋 الخطوات السريعة للنشر

### 1️⃣ دفع الكود إلى GitHub
```bash
cd /home/sabry/Downloads/menuqr/Backend
git init
git add .
git commit -m "Add integrated AI service with Groq LLM"
git remote add origin https://github.com/sabry660/menuqr-backend.git
git push -u origin main
```

### 2️⃣ إعداد قاعدة البيانات على Neon (مجاني)
1. **اذهب إلى:** [console.neon.tech](https://console.neon.tech/)
2. **أنشئ project جديد:** `menuqr-db`
3. **اختر Region:** AWS us-east-1 (أو الأقرب لموقعك)
4. **انسخ Connection String:**
   ```
   postgresql://neondb_owner:PASSWORD@ep-xxxxx.us-east-1.aws.neon.tech/menuqr?sslmode=require
   ```

### 3️⃣ نشر Backend على Render (مجاني)
1. **اذهب إلى:** [dashboard.render.com](https://dashboard.render.com/)
2. **New -> Web Service**
3. **Connect GitHub:** `sabry660/menuqr-backend`
4. **الإعدادات:**
   - Name: `menuqr-backend`
   - Region: Oregon
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### 4️⃣ إضافة Environment Variables في Render
```bash
# AI Service
GROQ_API_KEY=your_groq_api_key_here
AI_SERVICE_API_KEY=your_ai_service_api_key_here

# Database (من Neon)
DATABASE_URL=postgresql://neondb_owner:PASSWORD@ep-xxxxx.us-east-1.aws.neon.tech/menuqr?sslmode=require

# Security
JWT_SECRET=7f0d8f08d584954c2671c9f54b771c6d2092669e0ba54a323600feb234f1c02f

# Environment
APP_ENV=production
CORS_ORIGINS=https://your-frontend-domain.com
```

### 5️⃣ تشغيل Migrations
**استخدم Neon SQL Editor:**
```sql
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
```

### 6️⃣ اختبار الـ API
```bash
# Health check
curl https://menuqr-backend.onrender.com/health

# AI health check  
curl https://menuqr-backend.onrender.com/api/v1/ai/health

# Swagger docs
https://menuqr-backend.onrender.com/docs
```

## ✅ ما تحتاجه للبدء:

- ✅ GitHub repository: `https://github.com/sabry660/menuqr-backend.git`
- ✅ GROQ_API_KEY: موجود بالفعل
- ✅ Code جاهز مع AI service متكامل
- ✅ Docker/Render configuration جاهز

## 🎯 مزايا هذا الإعداد:

- **Neon:** مجاني، serverless، لا ينام أبداً
- **Render:** مجاني، auto SSL، GitHub integration
- **AI Service:** متكامل مع Groq LLM
- **Port:** لا يوجد conflicts (8000 فقط)

## 📚 للتفاصيل الكاملة:
راجع `DEPLOYMENT_GUIDE.md` للخطوات التفصيلية.

---

**الخطوة التالية:** ابدأ من الخطوة 1 وأكمل بالترتيب! 🚀