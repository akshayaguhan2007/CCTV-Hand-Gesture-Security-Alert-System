@echo off
REM Adjust remote URL if necessary
set "REPO_URL=https://github.com/akshayaguhan2007/CCTV-Hand-Gesture-Security-Alert-System.git"

REM Optional: install Git LFS and track common large file types
git lfs install

REM Track typical model files (safe to run multiple times)
git lfs track "*.h5" "*.pt" "*.pth" "*.ckpt" "*.model" 2>nul

REM Add .gitattributes if created by LFS tracking
git add .gitattributes 2>nul

REM Stage changes
git add .

REM Commit if there are staged changes
git commit -m "Prepare project for GitHub" || echo No changes to commit.

REM Ensure main branch
git branch -M main

REM Add or update remote
git remote get-url origin >nul 2>&1
if %ERRORLEVEL%==0 (
    git remote set-url origin %REPO_URL%
) else (
    git remote add origin %REPO_URL%
)

REM Push
git push -u origin main
echo Done.
