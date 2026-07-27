"""Build an import-ready Power BI showcase package for InternLens AI."""
import csv, json, random, shutil
from datetime import date, timedelta
from pathlib import Path

random.seed(20260725)
root = Path("PowerBI_InternLens_Showcase")
if root.exists(): shutil.rmtree(root)
data_dir = root / "data"; data_dir.mkdir(parents=True)

def write_csv(name, rows):
    rows = list(rows)
    with (data_dir / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)

faculty = [{"FacultyID": f"FAC-{i:03d}", "FacultyName": n, "Department": d} for i,(n,d) in enumerate([
    ("Dr. Aisha Khan","Computer Science"),("Prof. Rohan Mehta","Data Analytics"),("Dr. Neha Sharma","AI & ML"),
    ("Prof. Arjun Rao","Software Engineering"),("Dr. Isha Patel","Cybersecurity"),("Prof. Kabir Singh","Cloud Computing")], 1)]
classrooms = [{"ClassroomID":f"CLS-{i:02d}","ClassroomName":n,"FacultyID":faculty[(i-1)%6]["FacultyID"],"Program":p} for i,(n,p) in enumerate([
    ("Neural-Ops Systems Lab","B.Tech CSE"),("Presentation Systems Lab","B.Tech CSE"),("Cloud Engineering Studio","B.Tech IT"),
    ("Data Storytelling Lab","BCA"),("Secure Software Lab","B.Tech CSE"),("Career Readiness Cohort","MCA")],1)]
students=[]
for i in range(1,81):
    risk=random.choices(["Low","Medium","High"],[.55,.30,.15])[0]
    attendance=round(random.uniform(80,98) if risk=="Low" else random.uniform(62,84) if risk=="Medium" else random.uniform(42,67),1)
    students.append({"StudentID":f"STU-{i:04d}","StudentName":f"Student {i:02d}","Program":["B.Tech CSE","B.Tech IT","BCA","MCA"][i%4],"Semester":(i%8)+1,"ClassroomID":classrooms[i%6]["ClassroomID"],"AttendancePct":attendance,"RiskBand":risk,"PlacementEligible":"Yes" if attendance>=65 else "No"})

start=date(2026,1,1); attendance=[]; predictions=[]; evaluations=[]; leaves=[]; tasks=[]; submissions=[]
criteria=["Content clarity","Technical depth","Delivery & confidence","Visual design","Question handling"]
for st in students:
    base=st["AttendancePct"]; success=round(min(98,max(28,base*.38+random.uniform(28,49))),1)
    placement=round(min(96,max(20,success+random.uniform(-8,8))),1)
    predictions.append({"StudentID":st["StudentID"],"PredictionDate":"2026-07-25","AcademicSuccessProbability":success,"PlacementProbability":placement,"PerformanceRating":"Excellent" if success>=82 else "Strong" if success>=68 else "Developing" if success>=52 else "At Risk","RiskScore":round(100-success,1)})
    for m in range(7):
        dt=start+timedelta(days=m*28)
        attendance.append({"StudentID":st["StudentID"],"Date":dt.isoformat(),"Month":dt.strftime("%b"),"AttendancePct":round(max(35,min(100,base+random.uniform(-12,8))),1)})
    for p in range(1,4):
        avg=round(max(42,min(99,success+random.uniform(-15,15))),1)
        for c in criteria:
            score=round(max(35,min(100,avg+random.uniform(-10,10))),1)
            evaluations.append({"EvaluationID":f"PRE-{st['StudentID'][-4:]}-{p}","StudentID":st["StudentID"],"FacultyID":classrooms[[x['ClassroomID'] for x in classrooms].index(st['ClassroomID'])]["FacultyID"],"EvaluationDate":(start+timedelta(days=35*p)).isoformat(),"Criterion":c,"Score":score,"ShowMarks":"Yes" if p!=2 else "No","ImprovementNote":"Improve pacing and use one clearer real-world example."})
    if random.random()<.35:
        accepted=random.random()<.72
        leaves.append({"RequestID":f"LR-{st['StudentID'][-4:]}","StudentID":st["StudentID"],"FacultyID":classrooms[[x['ClassroomID'] for x in classrooms].index(st['ClassroomID'])]["FacultyID"],"RequestDate":(start+timedelta(days=random.randint(20,190))).isoformat(),"Reason":random.choice(["Medical leave","Family emergency","Internet outage"]),"Status":"Approved" if accepted else "Rejected","MLCreditAdjustment":5 if accepted else -5})

for i in range(1,31):
    cls=classrooms[(i-1)%6]; due=start+timedelta(days=i*6)
    tasks.append({"TaskID":f"TSK-{i:03d}","ClassroomID":cls["ClassroomID"],"TaskTitle":random.choice(["API Integration","Data Story","Cloud Deployment","Security Review","Presentation Brief"]),"DueDate":due.isoformat(),"Category":random.choice(["Assignment","Presentation","Lab"] )})
for task in tasks:
    for st in [x for x in students if x["ClassroomID"]==task["ClassroomID"]]:
        score=round(max(35,min(100,st["AttendancePct"]+random.uniform(-23,15))),1)
        submissions.append({"SubmissionID":f"SUB-{task['TaskID'][-3:]}-{st['StudentID'][-4:]}","TaskID":task["TaskID"],"StudentID":st["StudentID"],"SubmittedDate":(date.fromisoformat(task['DueDate'])+timedelta(days=random.randint(-3,5))).isoformat(),"Status":random.choices(["Approved","Pending","Late"],[.72,.12,.16])[0],"Marks":score})

for name, rows in {"Students.csv":students,"Faculty.csv":faculty,"Classrooms.csv":classrooms,"Attendance.csv":attendance,"Predictions.csv":predictions,"PresentationEvaluations.csv":evaluations,"LeaveRequests.csv":leaves,"Tasks.csv":tasks,"Submissions.csv":submissions}.items(): write_csv(name,rows)

theme={"name":"InternLens Intelligence","dataColors":["#F27D26","#00D2FF","#28C76F","#F6C344","#EA5455","#8F5FE8"],"background":"#090B0F","foreground":"#F1F2F6","tableAccent":"#F27D26","visualStyles":{"*":{"*":{"title":[{"show":True,"color":{"solid":{"color":"#F1F2F6"}},"fontFamily":"Inter"}],"labels":[{"color":{"solid":{"color":"#CBD5E1"}},"fontFamily":"Inter"}]}}}}
(root/"InternLens_Theme.json").write_text(json.dumps(theme,indent=2),encoding="utf-8")

dax="""Total Students = DISTINCTCOUNT(Students[StudentID])\nAverage Success Probability = AVERAGE(Predictions[AcademicSuccessProbability])\nAverage Placement Probability = AVERAGE(Predictions[PlacementProbability])\nAt Risk Students = CALCULATE([Total Students], Students[RiskBand] = \"High\")\nApproved Leave Rate = DIVIDE(CALCULATE(COUNTROWS(LeaveRequests), LeaveRequests[Status] = \"Approved\"), COUNTROWS(LeaveRequests))\nAverage Presentation Score = AVERAGE(PresentationEvaluations[Score])\nOn-Time Submission Rate = DIVIDE(CALCULATE(COUNTROWS(Submissions), Submissions[Status] = \"Approved\"), COUNTROWS(Submissions))\n"""
(root/"DAX_Measures.txt").write_text(dax,encoding="utf-8")

readme="""# InternLens AI — Power BI Showcase\n\nOpen `InternLens_Showcase.pbip` in Power BI Desktop (enable **Power BI Project (.pbip) save option** in Preview features). Import every CSV in `data/` using **Get data > Text/CSV**, then apply `InternLens_Theme.json` from **View > Themes > Browse for themes**.\n\n## Relationships\n- Students[StudentID] -> Attendance, Predictions, PresentationEvaluations, LeaveRequests, Submissions[StudentID]\n- Faculty[FacultyID] -> Classrooms, PresentationEvaluations, LeaveRequests[FacultyID]\n- Classrooms[ClassroomID] -> Students, Tasks[ClassroomID]\n- Tasks[TaskID] -> Submissions[TaskID]\n\n## Report pages\n1. **Executive Command Center** — KPI cards: Total Students, Avg Success, Avg Placement, At Risk; risk donut; success by program; monthly attendance line.\n2. **Academic & ML Performance** — scatter: Attendance vs Success (size=Placement); risk-band stacked column; performance-rating bar; prediction table.\n3. **Presentation Intelligence** — average score by criterion; score trend by evaluation date; show-marks visibility donut; student drill-through table.\n4. **Leave & Engagement** — approved/rejected leave waterfall using MLCreditAdjustment; leave reasons bar; on-time submission rate; task status matrix.\n\nUse `DAX_Measures.txt` for measures. All data is fictional and designed for demonstration.\n"""
(root/"README.md").write_text(readme,encoding="utf-8")

# PBIP pointer and editable project metadata. The report's visual canvas is deliberately left for Desktop creation after importing the data.
(root/"InternLens_Showcase.pbip").write_text(json.dumps({"version":"1.0","artifacts":[{"report":{"path":"InternLens_Showcase.Report"}}]},indent=2),encoding="utf-8")
report=root/"InternLens_Showcase.Report"; report.mkdir()
(report/"definition.pbir").write_text(json.dumps({"$schema":"https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json","version":"4.0","datasetReference":{"byPath":{"path":"../InternLens_Showcase.SemanticModel"}}},indent=2),encoding="utf-8")
model=root/"InternLens_Showcase.SemanticModel"; model.mkdir()
(model/"definition.pbism").write_text(json.dumps({"$schema":"https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/2.0.0/schema.json","version":"4.0"},indent=2),encoding="utf-8")
(root/".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n",encoding="utf-8")
print(root)
