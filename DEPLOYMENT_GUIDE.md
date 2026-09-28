# 🚀 MenuQR Backend Deployment Guide (Neon DB + Render Backend)

## 📋 الخطوات التفصيلية للنشر على Neon + Render

### 1️⃣ إعداد Repository على GitHub

```bash
# تأكد من أنك في المجلد الصحيح
cd /home/sabry/Downloads/menuqr/Backend

# إعداد Git إذا لم يكن موجود
git init
git add .
git commit -m "Add integrated AI service with Groq LLM"

# ربط بـ GitHub (موجود بالفعل: https://github.com/sabry660/menuqr-backend.git)
git remote add origin https://github.com/sabry660/menuqr-backend.git
git push -u origin main
```

### 2️⃣ إعداد PostgreSQL على Neon (مجاني)

1. **اذهب إلى [Neon Console](https://console.neon.tech/)**
2. **سجل دخول أو إنشاء حساب مجاني**
3. **اذهب إلى "Create a project"**
4. **أدخل الإعدادات:**
   - Project Name: `menuqr-db`
   - Region: اختيار المنطقة الأقرب لموقعك (مثل: AWS us-east-1)
   - PostgreSQL Version: 16 (أو الأحدث)
5. **انقر "Create Project"**
6. **انتظر حتى يتم إنشاء الـ project**
7. **انسخ Connection String من Neon Dashboard:**
   - اذهب إلى SQL Editor أو Connection Details
   - انسخ الـ Connection string (سيكون مثل: `postgresql://neondb_owner:xxxx@ep-xxxxx.us-east-1.aws.neon.tech/neondb?sslmode=require`)
8. **عدّل الـ connection string ليتوافق مع التطبيق:**
   - قم بتغيير `neondb` إلى `menuqr` في اسم الـ database
   - النتيجة النهائية: `postgresql://neondb_owner:xxxx@ep-xxxxx.us-east-1.aws.neon.tech/menuqr?sslmode=require`

### 3️⃣ إعداد Redis على Render (اختياري لكن موصى به)

1. **اذهب إلى [Render Dashboard](https://dashboard.render.com/)**
2. **سجل دخول أو إنشاء حساب مجاني**
3. **اذهب إلى "New" -> "Redis"**
4. **أدخل الإعدادات:**
   - Name: `menuqr-redis`
   - Region: Oregon (أو الأقرب لموقعك)
   - Plan: Free
5. **انقر "Create Redis"**
6. **انسخ "Internal Redis URL" من Dashboard**

### 4️⃣ نشر الـ Backend على Render

1. **اذهب إلى [Render Dashboard](https://dashboard.render.com/)**
2. **اذهب إلى "New" -> "Web Service"**
3. **Connect إلى GitHub repository:**
   - اختر `sabry660/menuqr-backend`
   - Branch: `main`
4. **أدخل الإعدادات:**
   - Name: `menuqr-backend`
   - Region: Oregon (أو المنطقة الأقرب لـ Neon)
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. **أضف Environment Variables (مهم جداً):**

#### انقر على "Advanced" -> "Add Environment Variable" وأضف:

```bash
# AI Service (مهم جداً)
GROQ_API_KEY=your_groq_api_key_here
AI_SERVICE_API_KEY=your_ai_service_api_key_here

# Database (من Neon - مهم جداً)
DATABASE_URL=postgresql://neondb_owner:PASSWORD@ep-xxxxx.us-east-1.aws.neon.tech/menuqr?sslmode=require

# Redis (من Render Dashboard - اختياري)
REDIS_URL=redis://default:PASSWORD@redis-xxxxx.oregon.render.com:6379

# Security
JWT_SECRET=7f0d8f08d584954c2671c9f54b771c6d2092669e0ba54a323600feb234f1c02f

# Environment
APP_ENV=production
LOG_LEVEL=INFO

# CORS (عدّل حسب frontend domain)
CORS_ORIGINS=https://your-frontend-domain.com
FRONTEND_URL=https://your-frontend-domain.com
```

6. **انقر "Create Web Service"**
7. **انتظر حتى يكتمل الـ build والـ deployment** (قد يستغرق 5-10 دقائق)

### 5️⃣ تشغيل Database Migrations

بعد نجاح الـ deployment:

#### الخيار 1: استخدام Neon SQL Editor (موصى به)
1. **اذهب إلى Neon Console -> SQL Editor**
2. **شغل الأوامر التالية:**
```sql
-- إنشاء جدول alembic_version إذا لم يكن موجود
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- إدخال الإصدار الحالي (استبدل بالرقم الصحيح من alembic/versions)
--INSERT INTO alembic_version (version_num) VALUES ('xxxxxxxxxxxx');
```

#### الخيار 2: استخدام Render Shell
1. **اذهب إلى Render Dashboard -> menuqr-backend -> "Shell"**
2. **شغل الأوامر التالية:**
```bash
# تفعيل الـ virtual environment
source /opt/venv/bin/activate

# تشغيل alembic migrations
alembic upgrade head
```

### 6️⃣ اختبار الـ API

1. **اذهب إلى Render Dashboard -> menuqr-backend -> "Domains"**
2. **انسخ الـ URL (مثل: https://menuqr-backend.onrender.com)**
3. **اختبر الـ endpoints:**

```bash
# Health check
curl https://menuqr-backend.onrender.com/health

# AI health check
curl https://menuqr-backend.onrender.com/api/v1/ai/health

# Swagger documentation
https://menuqr-backend.onrender.com/docs
```

### 7️⃣ إعداد Frontend (إذا وجد)

1. **عدّل CORS_ORIGINS في Render Environment Variables:**
```bash
CORS_ORIGINS=https://your-frontend.vercel.app,https://your-frontend-domain.com
```

## 🎯 مزايا استخدام Neon + Render

### Neon Database:
- ✅ **مجاني للمشاريع الصغيرة** (0.5 GB storage)
- ✅ **Serverless** - لا يحتاج إدارة
- ✅ **Auto-scaling** - يتكيف مع الحمل
- ✅ **Connection pooling** - أداء أفضل
- ✅ **Branching** - لـ testing و development
- ✅ **No sleep mode** - دائماً متاح (خلافاً لـ Render PostgreSQL)

### Render Backend:
- ✅ **مجاني للمشاريع الصغيرة**
- ✅ **Auto SSL certificates**
- ✅ **GitHub integration** - auto deployment
- ✅ **Easy environment variables management**
- ✅ **Built-in monitoring و logs**

## ⚠️ ملاحظات مهمة

### للنسخة المجانية:
- **Neon:** 0.5 GB storage مجاني، لا ينام أبداً
- **Render Web Service:** ينام بعد 15 دقيقة (يستيقظ خلال 30 ثانية)
- **Render Redis:** ينام بعد 7 أيام من عدم النشاط
- **Render Build time:** محدود بـ 15 دقيقة لكل build

### تحسينات للأداء:
- استخدم Neon connection pooling
- استخدم Redis للـ caching
- قلل الـ logs في الـ production
- استخدم CDN للـ static files

### الأمان:
- لا تشارك الـ API keys
- استخدم HTTPS فقط (مفعّل تلقائياً على Render)
- قم بتحديث الـ dependencies بانتظام
- استخدم SSL mode في Neon connection string

## 🔧 استكشاف الأخطاء

### إذا فشل الـ build:
1. تأكد من أن `requirements.txt` يحتوي على جميع المكتبات
2. تأكد من أن Python version متوافق (3.13)
3. راجع الـ build logs في Render Dashboard

### إذا فشل الـ database connection:
1. تأكد من DATABASE_URL صحيح من Neon
2. تأكد من استخدام `sslmode=require` في connection string
3. تحقق من أن Neon project نشط
4. راجع Neon logs في Dashboard

### إذا فشل AI service:
1. تأكد من GROQ_API_KEY صحيح
2. اختبر الـ endpoint `/api/v1/ai/health`
3. راجع الـ logs للـ AI errors

### مشاكل Neon خاصة:
1. **Connection timeout:** استخدم connection pooling
2. **Storage limit:** راجع Neon Dashboard
3. **Region mismatch:** اختر نفس المنطقة لـ Render

## 📞 المساعدة

إذا واجهت مشاكل:
1. راجع Render logs: Dashboard -> Web Service -> Logs
2. راجع Neon logs: Console -> Logs
3. تأكد من Environment Variables صحيحة
4. تحقق من أن جميع dependencies مثبتة

---

**ملاحظة:** الملف `render.yaml` موجود في المجلد ويمكن استخدامه أيضاً للـ deployment عبر Render CLI.