# SafeSign

To push this project to GitHub, run these commands in project root:

1. (Optional) Install and configure Git LFS for large files:
   - git lfs install
   - git lfs track "*.h5" "*.pt" "*.pth" "*.ckpt" "*.model"
   - git add .gitattributes

2. Stage and commit:
   - git add .
   - git commit -m "Prepare project for GitHub"

3. Add remote and push:
   - git branch -M main
   - git remote add origin https://github.com/akshayaguhan2007/CCTV-Hand-Gesture-Security-Alert-System.git
   - git push -u origin main

Notes:
- Ensure files >100MB are tracked with LFS before committing.
- If the remote already exists, use: git remote set-url origin <url>.
- If you prefer a script, run push_to_github.bat (Windows) provided in this folder.
