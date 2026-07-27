# InternLens AI — Power BI Showcase

Open `InternLens_Showcase.pbip` in Power BI Desktop (enable **Power BI Project (.pbip) save option** in Preview features). Import every CSV in `data/` using **Get data > Text/CSV**, then apply `InternLens_Theme.json` from **View > Themes > Browse for themes**.

## Relationships
- Students[StudentID] -> Attendance, Predictions, PresentationEvaluations, LeaveRequests, Submissions[StudentID]
- Faculty[FacultyID] -> Classrooms, PresentationEvaluations, LeaveRequests[FacultyID]
- Classrooms[ClassroomID] -> Students, Tasks[ClassroomID]
- Tasks[TaskID] -> Submissions[TaskID]

## Report pages
1. **Executive Command Center** — KPI cards: Total Students, Avg Success, Avg Placement, At Risk; risk donut; success by program; monthly attendance line.
2. **Academic & ML Performance** — scatter: Attendance vs Success (size=Placement); risk-band stacked column; performance-rating bar; prediction table.
3. **Presentation Intelligence** — average score by criterion; score trend by evaluation date; show-marks visibility donut; student drill-through table.
4. **Leave & Engagement** — approved/rejected leave waterfall using MLCreditAdjustment; leave reasons bar; on-time submission rate; task status matrix.

Use `DAX_Measures.txt` for measures. All data is fictional and designed for demonstration.
