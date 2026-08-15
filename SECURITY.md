# 🔒 celia.pro Security Policy

**Last Updated:** 2026-08-14  
**Version:** 2.0.0

---

## 📋 Overview

celia.pro takes security seriously. This document outlines our security practices, reporting procedures, and the measures we've implemented to protect our users and our intellectual property.

---

## 🚨 Reporting Security Vulnerabilities

### If you discover a security vulnerability:

1. **DO NOT** create a public issue
2. **DO NOT** disclose the vulnerability publicly
3. **Email us immediately:** security@celia.pro

### What to include in your report:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Our response:

- We will acknowledge receipt within 24 hours
- We will investigate and provide an initial assessment within 72 hours
- We will work on a fix and coordinate disclosure with you

---

## 🛡️ Security Measures Implemented

### 1. **Input Validation**
All user inputs are validated and sanitized:
- Message length limits (10,000 characters)
- Code execution sandboxing
- Path traversal prevention
- Shell command whitelist

### 2. **Rate Limiting**
- 30 requests per 60 seconds per client
- Token bucket algorithm
- Automatic blocking of abusive clients

### 3. **CORS Hardening**
- Specific origins only (no wildcard `*`)
- Strict origin validation
- Secure headers

### 4. **Sandbox Execution**
Code execution runs in isolated sandboxes:
- Blocked dangerous imports (`os`, `subprocess`, `sys`)
- Prevented class hierarchy access (`__class__`, `__bases__`)
- No file system access outside workspace

### 5. **Prompt Injection Protection**
- Pattern detection for injection attempts
- Output sanitization
- Boundary markers for tool outputs

### 6. **Circuit Breaker Pattern**
- Automatic failover between LLM providers
- Health monitoring
- Recovery timeouts

### 7. **Audit Logging**
- All tool executions logged
- Request tracking with unique IDs
- Structured JSON logs
- No sensitive data in logs

### 8. **Secret Management**
- No API keys in source code
- User-provided keys via secure UI
- Secret masking in logs and responses
- Environment variable isolation

---

## 🔐 Supported & Unsupported Versions

| Version | Supported |
|---------|-----------|
| 2.0.0   | ✅ Current |
| 1.x.x   | ❌ End of Life |

---

## 🚫 What We Don't Support

- Modifications to the source code
- Third-party integrations without approval
- Deployment on unauthorized servers
- Reverse engineering attempts

---

## 📞 Contact

**Security Team:** security@celia.pro  
**General Inquiries:** info@celia.pro  
**Licensing:** licensing@celia.pro

---

## ⚖️ Legal Notice

This software is protected under international copyright laws. Any attempt to bypass security measures, reverse engineer the software, or use it without explicit permission is strictly prohibited and may result in legal action.

---

© 2026 celia.pro. All rights reserved.
