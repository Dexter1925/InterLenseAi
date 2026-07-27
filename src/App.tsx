import { useState } from "react";
import { 
  Bot, 
  ChevronRight, 
  Compass, 
  Cpu, 
  Eye, 
  GraduationCap, 
  Heart, 
  Network, 
  ShieldCheck, 
  Sparkles, 
  Target, 
  User, 
  Layers, 
  FolderGit2, 
  Terminal,
  Activity
} from "lucide-react";
import ParticleGlobe from "./components/ParticleGlobe";
import StudentDashboard from "./components/StudentDashboard";
import FacultyDashboard from "./components/FacultyDashboard";
import { RoleMode } from "./types";

export default function App() {
  const [roleMode, setRoleMode] = useState<RoleMode>("landing");
  const [isApiAvailable] = useState(true);

  return (
    <div className="min-h-screen bg-brand-bg text-zinc-400 font-sans selection:bg-brand-primary selection:text-black relative overflow-x-hidden pb-12">
      {/* Dynamic Background Grid Mesh */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1A1A1E_1px,transparent_1px),linear-gradient(to_bottom,#1A1A1E_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] opacity-45 pointer-events-none" />

      {/* Futuristic Header Navbar */}
      <header className="sticky top-0 z-40 bg-brand-bg/90 backdrop-blur-md border-b border-zinc-800/80 shadow-lg">
        <div className="max-w-7xl mx-auto px-6 h-18 flex items-center justify-between">
          
          {/* Logo Brand */}
          <div 
            onClick={() => setRoleMode("landing")}
            className="flex items-center gap-3 cursor-pointer group"
          >
            <div className="relative w-9 h-9 bg-brand-primary flex items-center justify-center border-2 border-white">
              <Network className="w-5 h-5 text-black" />
            </div>
            <div>
              <span className="font-display font-black text-xl text-white tracking-tighter uppercase">INTERNLENS</span>
              <span className="text-black text-[10px] font-mono font-bold tracking-widest uppercase ml-1.5 bg-brand-primary border border-brand-primary px-1.5 py-0.5">
                AI
              </span>
            </div>
          </div>

          {/* Navigation Controls */}
          <nav className="hidden md:flex items-center gap-1 bg-zinc-900 border border-zinc-800 p-1">
            <button
              onClick={() => setRoleMode("landing")}
              className={`px-4.5 py-2 text-xs font-black uppercase tracking-wider transition-all flex items-center gap-2 ${
                roleMode === "landing" 
                  ? "bg-brand-primary text-black" 
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <Compass className="w-4 h-4" />
              <span>Portal Explorer</span>
            </button>
            <button
              onClick={() => setRoleMode("student")}
              className={`px-4.5 py-2 text-xs font-black uppercase tracking-wider transition-all flex items-center gap-2 ${
                roleMode === "student" 
                  ? "bg-brand-primary text-black" 
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <GraduationCap className="w-4 h-4" />
              <span>Alex (Student)</span>
            </button>
            <button
              onClick={() => setRoleMode("faculty")}
              className={`px-4.5 py-2 text-xs font-black uppercase tracking-wider transition-all flex items-center gap-2 ${
                roleMode === "faculty" 
                  ? "bg-brand-primary text-black" 
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <Cpu className="w-4 h-4" />
              <span>Dr. Aris (Faculty)</span>
            </button>
          </nav>

          {/* Status Indicators & Login button */}
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500">
              <span className="w-2 h-2 bg-brand-primary animate-pulse inline-block"></span>
              <span>Gemini AI Connected</span>
            </div>
            
            {roleMode === "landing" ? (
              <button 
                onClick={() => setRoleMode("student")}
                className="bg-white text-black font-black uppercase text-xs tracking-wider px-5 py-3 border border-transparent hover:bg-brand-primary transition-all flex items-center gap-1.5"
              >
                <span>Enter Portals</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            ) : (
              <button 
                onClick={() => setRoleMode("landing")}
                className="bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 font-black uppercase text-xs tracking-wider px-5 py-3 text-white transition-all"
              >
                Sign Out
              </button>
            )}
          </div>

        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-6 pt-10 relative">
        
        {/* LANDING PAGE VIEW */}
        {roleMode === "landing" && (
          <div className="space-y-16">
            
            {/* Hero Split Frame */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center relative py-8">
              
              {/* Hero Copy (Left 7 cols) */}
              <div className="lg:col-span-7 space-y-6 relative z-10">
                <div className="flex flex-col space-y-1">
                  <span className="text-brand-primary uppercase text-xs tracking-[0.4em] font-black">
                    NEXT-GEN COHORT ANALYSIS
                  </span>
                  <div className="h-[2px] w-12 bg-brand-primary mt-2"></div>
                </div>

                <h1 className="text-5xl sm:text-6xl lg:text-8xl font-black font-display tracking-tighter text-white leading-[0.9] uppercase max-w-2xl">
                  LUMINOUS <br />
                  <span className="text-transparent text-stroke-sm" style={{ WebkitTextStroke: "1px rgba(255,255,255,0.4)" }}>ANALYTICS</span> <br />
                  FOR <span className="text-brand-primary">GROWTH</span>
                </h1>

                <p className="text-zinc-400 text-sm sm:text-base leading-relaxed max-w-xl font-medium">
                  Deep competency mapping, real-time student tracking, automated document pre-grading, and Gemini-guided career coaching combined in an immersive space.
                </p>

                {/* Call to Actions */}
                <div className="flex flex-wrap items-center gap-4 pt-4">
                  <button 
                    onClick={() => setRoleMode("student")}
                    className="bg-brand-primary text-black font-black uppercase text-xs tracking-wider px-7 py-4 border-2 border-brand-primary hover:bg-white hover:border-white transition-all flex items-center gap-2"
                  >
                    <GraduationCap className="w-5 h-5" />
                    <span>Alex (Student Portal)</span>
                  </button>

                  <button 
                    onClick={() => setRoleMode("faculty")}
                    className="bg-transparent hover:bg-white/10 border-2 border-white text-white font-black uppercase text-xs tracking-wider px-6 py-4 transition-all flex items-center gap-2"
                  >
                    <Cpu className="w-5 h-5 text-brand-primary" />
                    <span>Faculty Co-Pilot</span>
                  </button>
                </div>
              </div>

              {/* Glowing Interactive Particle Globe (Right 5 cols) */}
              <div className="lg:col-span-5 h-[350px] sm:h-[450px] relative flex items-center justify-center">
                {/* Floating neon orbit background circles */}
                <div className="absolute w-72 h-72 rounded-full border border-brand-primary/10 animate-spin" style={{ animationDuration: "25s" }} />
                <div className="absolute w-80 h-80 rounded-full border border-dashed border-brand-secondary/5 animate-spin" style={{ animationDuration: "35s" }} />
                <div className="absolute w-60 h-60 bg-brand-primary/5 blur-[80px] rounded-full" />
                
                {/* Canvas 3D particle globe */}
                <ParticleGlobe />
              </div>

            </div>

            {/* Quick Portal Switcher Feature Flags Banner */}
            <div className="glass-panel p-6 rounded-none border border-zinc-800 flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-brand-primary/10 border-2 border-brand-primary flex items-center justify-center">
                  <Bot className="w-5.5 h-5.5 text-brand-primary" />
                </div>
                <div>
                  <h4 className="text-xs font-black uppercase tracking-wider text-white">Full-Stack Capability Configured</h4>
                  <p className="text-xs text-zinc-400 mt-0.5">Dynamic Express server APIs with in-memory persistence loaded.</p>
                </div>
              </div>
              <div className="flex gap-2">
                <button 
                  onClick={() => setRoleMode("student")}
                  className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 rounded-none text-xs font-black uppercase tracking-wider text-white border border-zinc-750 transition-all"
                >
                  Student Flow
                </button>
                <button 
                  onClick={() => setRoleMode("faculty")}
                  className="px-4 py-2 bg-brand-primary text-black rounded-none text-xs font-black uppercase tracking-wider border border-brand-primary hover:bg-white hover:border-white transition-all"
                >
                  Faculty Board
                </button>
              </div>
            </div>

            {/* Premium Intelligence Bento Grid */}
            <div className="space-y-6">
              <div className="flex flex-col space-y-1">
                <h3 className="text-xs font-mono font-black tracking-[0.35em] text-brand-primary uppercase">Precision Intelligence</h3>
                <h2 className="text-4xl font-black font-display text-white uppercase tracking-tight">Bento Core Features</h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
                
                {/* Bento Item 1: Auto tracking (4 cols) */}
                <div className="md:col-span-4 glass-panel p-6 rounded-none border border-zinc-800 flex flex-col justify-between h-[250px] relative overflow-hidden group hover:border-brand-primary transition-all cursor-pointer" onClick={() => setRoleMode("student")}>
                  <div className="absolute top-0 right-0 w-24 h-24 bg-brand-primary/5 blur-[30px] rounded-full group-hover:bg-brand-primary/10 transition-all" />
                  <div className="flex justify-between items-start">
                    <Target className="w-7 h-7 text-brand-primary" />
                    <span className="text-[10px] font-mono text-black bg-brand-primary px-2 py-0.5 uppercase font-black tracking-wider">Progress</span>
                  </div>
                  <div>
                    <h4 className="text-lg font-black font-display text-white uppercase tracking-tight group-hover:text-brand-primary transition-colors">Automated Progress Checks</h4>
                    <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">
                      Intuitive circular tracking with milestones divided in modular cohort stages.
                    </p>
                  </div>
                </div>

                {/* Bento Item 2: Competency radar (8 cols) */}
                <div className="md:col-span-8 glass-panel p-6 rounded-none border border-zinc-800 flex flex-col justify-between h-[250px] relative overflow-hidden group hover:border-brand-primary transition-all cursor-pointer" onClick={() => setRoleMode("student")}>
                  <div className="absolute -right-6 -bottom-6 w-48 h-48 bg-brand-primary/5 blur-[50px] rounded-full group-hover:bg-brand-primary/10 transition-all" />
                  <div className="flex justify-between items-start">
                    <Layers className="w-7 h-7 text-brand-primary" />
                    <span className="text-[10px] font-mono text-black bg-brand-primary px-2 py-0.5 uppercase font-black tracking-wider">Radar Map</span>
                  </div>
                  <div className="max-w-md">
                    <h4 className="text-lg font-black font-display text-white uppercase tracking-tight group-hover:text-brand-primary transition-colors">Competency Skill Analysis</h4>
                    <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">
                      Visualize technical, soft skills, and leadership competencies using dynamic interactive radar spiderweb polygons mapped directly from deliverables.
                    </p>
                  </div>
                </div>

                {/* Bento Item 3: AI Assistant (8 cols) */}
                <div className="md:col-span-8 glass-panel p-6 rounded-none border border-zinc-800 flex flex-col justify-between h-[250px] relative overflow-hidden group hover:border-brand-primary transition-all cursor-pointer" onClick={() => setRoleMode("student")}>
                  <div className="absolute top-0 right-0 w-36 h-36 bg-brand-primary/5 blur-[40px] rounded-full group-hover:bg-brand-primary/10 transition-all" />
                  <div className="flex justify-between items-start">
                    <Bot className="w-7 h-7 text-brand-primary" />
                    <span className="text-[10px] font-mono text-black bg-brand-primary px-2 py-0.5 uppercase font-black tracking-wider">Gemini 3.5</span>
                  </div>
                  <div className="max-w-md">
                    <h4 className="text-lg font-black font-display text-white uppercase tracking-tight group-hover:text-brand-primary transition-colors">AI Career Coaching & Bot</h4>
                    <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">
                      Ask anything about your Neural-Ops Systems internship track, get resume polish checklists, or prepare outline reviews with your integrated carrier assistant.
                    </p>
                  </div>
                </div>

                {/* Bento Item 4: Automated pre grading (4 cols) */}
                <div className="md:col-span-4 glass-panel p-6 rounded-none border border-zinc-800 flex flex-col justify-between h-[250px] relative overflow-hidden group hover:border-brand-primary transition-all cursor-pointer" onClick={() => setRoleMode("student")}>
                  <div className="absolute bottom-0 right-0 w-24 h-24 bg-brand-primary/5 blur-[30px] rounded-full group-hover:bg-brand-primary/10 transition-all" />
                  <div className="flex justify-between items-start">
                    <ShieldCheck className="w-7 h-7 text-brand-primary" />
                    <span className="text-[10px] font-mono text-black bg-brand-primary px-2 py-0.5 uppercase font-black tracking-wider">Grading</span>
                  </div>
                  <div>
                    <h4 className="text-lg font-black font-display text-white uppercase tracking-tight group-hover:text-brand-primary transition-colors">Automated Pre-Grading</h4>
                    <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">
                      Our Express API reviews PDF/xlsx submissions instantly with AI, giving feedback on progress boards in real time.
                    </p>
                  </div>
                </div>

              </div>
            </div>

            {/* Humble Footer */}
            <footer className="pt-12 border-t border-zinc-800 flex flex-col sm:flex-row items-center justify-between text-xs text-zinc-500 gap-4">
              <div className="flex items-center gap-2">
                <Network className="w-4 h-4 text-brand-primary" />
                <span>InternLens AI Platform. All rights reserved.</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="hover:text-white transition-colors cursor-pointer">Security Overview</span>
                <span>•</span>
                <span className="hover:text-white transition-colors cursor-pointer">Dr. Aris Cohort Link</span>
              </div>
            </footer>

          </div>
        )}

        {/* STUDENT PORTAL VIEW */}
        {roleMode === "student" && <StudentDashboard />}

        {/* FACULTY PORTAL VIEW */}
        {roleMode === "faculty" && <FacultyDashboard />}

      </main>
    </div>
  );
}
