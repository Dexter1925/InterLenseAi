# Push to GitHub

Use this file as a quick reference for pushing your project to GitHub.

## 1. Initialize Git (if needed)

```bash
git init
git add .
git commit -m "Initial commit"
```

## 2. Create a GitHub repository

Create a new repository on GitHub, then link it locally:

```bash
git branch -M main
git remote add origin https://github.com/your-username/your-repo-name.git
git push -u origin main
```

## 3. Later pushes

```bash
git add .
git commit -m "Your message"
git push
```

## 4. If you already have a remote

```bash
git remote -v
git remote set-url origin https://github.com/your-username/your-repo-name.git
git push -u origin main
```
