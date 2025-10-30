# AI Tech Lead - Troubleshooting Guide

## Common Issues and Solutions

### 🔴 Issue: "GITHUB_PRIVATE_KEY not found in environment variables"

**Error Message:**
```
ERROR:agents.reporter_agent:GitHub authentication failed: GITHUB_PRIVATE_KEY not found in environment variables
```

**Root Cause:**
Environment variables are not properly configured or have incorrect names.

**Solution:**
1. **Check your `.env` file** in the project root directory
2. **Verify the variable names match exactly:**
   ```env
   GITHUB_APP_ID=your_app_id_here
   GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
   your_private_key_content_here
   -----END RSA PRIVATE KEY-----"
   GITHUB_WEBHOOK_SECRET=your_webhook_secret_here
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

3. **Common naming mistakes:**
   - ❌ `GITHUB_APP_PRIVATE_KEY` (incorrect)
   - ✅ `GITHUB_PRIVATE_KEY` (correct)

4. **Test your environment:**
   ```bash
   python test_env.py
   ```

### 🔴 Issue: Gemini API 404 Model Not Found

**Error Message:**
```
ERROR:agents.reviewer_agent:Error during AI code review: 404 models/gemini-pro is not found
```

**Solution:**
This has been fixed in the latest version. The code now uses `gemini-2.5-flash`. If you still see this error, make sure you have the latest code.

### 🔴 Issue: "'str' object has no attribute 'get'"

**Error Message:**
```
ERROR:agents.reporter_agent:Error in report generation/posting for PR: 'str' object has no attribute 'get'
```

**Solution:**
This has been fixed with comprehensive type checking. Make sure you have the latest version of the code.

### 🔴 Issue: "Method withRequester(Requester) must be called first"

**Error Message:**
```
ERROR:agents.reporter_agent:GitHub authentication failed: Method withRequester(Requester) must be called first
AssertionError: Method withRequester(Requester) must be called first
```

**Root Cause:**
Incompatibility with PyGithub 2.8.1+ authentication API changes.

**Solution:**
This has been fixed by updating the GitHub authentication code. The fix changes:
```python
# OLD (doesn't work with PyGithub 2.8.1+):
return Github(installation_auth.token)

# NEW (works with PyGithub 2.8.1+):
return Github(auth=installation_auth)
```

**Test the fix:**
```bash
python test_github_auth.py
```

### 🔴 Issue: Webhook returning 400 or 202 but failing

**Symptoms:**
- Webhook receives requests (200/202 status)
- But workflow fails with authentication errors
- Logs show partial success but report posting fails

**Solution:**
1. **Verify all environment variables are set correctly:**
   ```bash
   python test_env.py
   ```

2. **Restart your application** after fixing environment variables:
   ```bash
   # Stop the current process (Ctrl+C)
   # Then restart:
   python webhook_server.py  # or whatever command you use to start
   ```

3. **Check your GitHub App permissions:**
   - Contents: Read
   - Issues: Write
   - Pull requests: Write
   - Metadata: Read

### 🔴 Issue: "partial_failure" status in logs

**Symptoms:**
```
INFO:__main__:Background AI workflow completed for PR #X with status: partial_failure
```

**Meaning:**
- Code review completed successfully ✅
- Unit testing completed successfully ✅  
- Report generation failed ❌

**Most Common Cause:**
Environment variables issue (see above).

## 🧪 Testing Your Setup

### Quick Test Commands

1. **Test environment variables:**
   ```bash
   python test_env.py
   ```

2. **Test all fixes:**
   ```bash
   python test_fixes.py
   ```

3. **Test mixed content handling:**
   ```bash
   python test_mixed_content.py
   ```

### Expected Output When Everything Works

**Webhook logs should show:**
```
INFO:crew:Code review analysis completed
INFO:crew:Starting unit test generation for PR #X
INFO:crew:Unit testing workflow completed
INFO:crew:Creating report for PR #X
INFO:agents.reporter_agent:Generating comprehensive report for PR #X
INFO:agents.reporter_agent:Attempting to authenticate with GitHub for installation_id: XXXXX
INFO:agents.reporter_agent:Successfully posted comment XXXXX to PR #X
INFO:crew:AI Tech Lead workflow completed for PR #X
INFO:__main__:Background AI workflow completed for PR #X with status: completed ✅
```

## 🔧 Step-by-Step Fix Process

If you're still having issues, follow these steps:

### Step 1: Verify Environment Variables
```bash
python test_env.py
```
Should show all ✅ green checkmarks.

### Step 2: Check Your .env File
Make sure it looks like this:
```env
GITHUB_APP_ID=2038832
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAqHNTdOWVs6BujTM75d1RnsORzh30rd4f0ok4W21LrRX+KC6b
... (your full private key)
-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=1234
GEMINI_API_KEY=AIzaSyDZedGZPbCtiiaSGwht9y83H3moHT0JGCk
```

### Step 3: Restart Your Application
After fixing the .env file:
1. Stop your webhook server (Ctrl+C)
2. Restart it: `python webhook_server.py` (or your startup command)

### Step 4: Test with a Simple PR
Push a small change to trigger the webhook and check the logs.

## 📞 Getting Help

If you're still having issues after following this guide:

1. **Check the logs** for specific error messages
2. **Run the test scripts** to identify the exact problem
3. **Verify your GitHub App configuration** in GitHub settings
4. **Make sure ngrok is running** and the webhook URL is correct

## 🎯 Success Indicators

You'll know everything is working when:
- ✅ `python test_env.py` shows all green checkmarks
- ✅ Webhook logs show "status: completed" 
- ✅ GitHub PR gets an AI-generated comment with code review
- ✅ No error messages in the logs

## 📝 Common Environment Variable Issues

### Issue: Variables not loading
**Solution:** Make sure `.env` file is in the project root directory.

### Issue: Private key format errors
**Solution:** Keep the private key in quotes and include the full BEGIN/END markers.

### Issue: App ID not recognized
**Solution:** Use only the numeric App ID, not the app name.

### Issue: API key invalid
**Solution:** Generate a new Gemini API key from Google AI Studio.