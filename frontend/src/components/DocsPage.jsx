import React from 'react';
import { motion } from 'motion/react';
import { X, Book, Cpu, Layers, Activity, Database, Globe, Zap, Wind, BarChart3 } from 'lucide-react';

export default function DocsPage({ onClose }) {
  return (
    <div className="fixed inset-0 z-50 bg-[#0b0b0b] flex flex-col md:flex-row shadow-2xl">
      <div className="w-full md:w-64 bg-[#1a1a1a] border-r border-white/10 p-6 flex flex-col">
        <div className="flex items-center gap-3 mb-12">
          <div className="w-10 h-10 bg-white text-black rounded-xl flex items-center justify-center font-bold text-xl">D</div>
          <h1 className="text-xl font-medium">Docs</h1>
        </div>

        <nav className="space-y-2 flex-1">
          <div className="text-[10px] uppercase tracking-widest text-white/40 mb-4 px-2">Capabilities</div>
          <DocLink icon={Cpu} label="Algebra & Calculus" />
          <DocLink icon={Layers} label="Structural FEM" />
          <DocLink icon={Activity} label="Fluid Dynamics" />
          <DocLink icon={Database} label="Data & Plotting" />
          <DocLink icon={Zap} label="Circuit Analysis" />
          <DocLink icon={BarChart3} label="Statistics & Error" />
          <DocLink icon={Wind} label="Thermo & Physics" />
          <DocLink icon={Globe} label="Smart Router" />
        </nav>

        <button 
          onClick={onClose}
          className="mt-8 flex items-center gap-3 text-white/60 hover:text-white transition-colors px-2 py-2"
        >
          <X className="w-5 h-5" />
          <span>Close Help</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6 md:p-12">
        <div className="max-w-3xl mx-auto space-y-12 pb-24">
          <header>
            <h2 className="text-4xl font-bold mb-4 tracking-tighter">System Intelligence</h2>
            <p className="text-white/40 text-lg leading-relaxed">
              Jhaytee Kernel is a high-precision engineering computation studio. It combines LLM-based parameter extraction with deterministic numerical solvers.
            </p>
          </header>

          <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <FeatureCard 
              title="Differential Equations"
              description="Solves 1st and 2nd order linear ODEs with constant coefficients. Essential for modeling circuits and mass-spring systems."
            />
            <FeatureCard 
              title="Statistics & Error"
              description="Computes central tendency (mean/median), dispersion (std dev), and 95% confidence intervals for engineering datasets."
            />
            <FeatureCard 
              title="Solid Mechanics"
              description="Mohr's Circle analysis and Beam Deflection/Stress for cantilever and simply supported configurations."
            />
            <FeatureCard 
              title="Section Properties"
              description="Calculates Centroids, Moments of Inertia (Ixx, Iyy), and Radius of Gyration for complex section geometries."
            />
            <FeatureCard 
              title="Signal Analysis"
              description="Fourier Series decomposition for periodic signals and Laplace Transform tables for frequency domain analysis."
            />
            <FeatureCard 
              title="Control Systems"
              description="Transfer function stability analysis (Poles/Zeros), BIBO stability checks, and frequency response insights (Bode)."
            />
            <FeatureCard 
              title="Fluid Mechanics"
              description="Flow diagnostics, Hydrostatics, and Head Loss (Darcy-Weisbach) frictional calculations for steady pipe flow."
            />
            <FeatureCard 
              title="Structural FEM"
              description="Nodal analysis for 2D trusses and Euler-Bernoulli frames with real-time stress and displacement calculation."
            />
            <FeatureCard 
              title="Vibration Kernel"
              description="SHM characteristics: Natural frequency, damping ratios, and period analysis for mechanical oscillators."
            />
          </section>

          <section className="bg-white/5 rounded-3xl p-8 border border-white/10">
            <h3 className="text-2xl font-bold mb-6">Data Visualization v2.0</h3>
            <ul className="space-y-4 text-white/60">
              <li className="flex gap-4">
                <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 shrink-0"></div>
                <p><strong>Interactive Tables:</strong> Search, sort, and paginate through thousands of rows of uploaded CSV data.</p>
              </li>
              <li className="flex gap-4">
                <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 shrink-0"></div>
                <p><strong>Regression Analysis:</strong> Automatic linear/polynomial fitting for any numeric dataset with R² reporting.</p>
              </li>
              <li className="flex gap-4">
                <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 shrink-0"></div>
                <p><strong>Mechanical Analysis:</strong> Specialized stress-strain curve detection and elastic modulus estimation.</p>
              </li>
              <li className="flex gap-4">
                <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 shrink-0"></div>
                <p><strong>Export Hub:</strong> Download high-res PNG/SVG plots and cleaned CSV processed data directly from the chat.</p>
              </li>
            </ul>
          </section>

          <section>
            <h3 className="text-xl font-bold mb-4">The Routing Kernel</h3>
            <p className="text-white/40">
              Unlike traditional chatbots, our Gemini Router doesn't "hallucinate" math. It identifies your intent, extracts parameters, and passes them to our Python-powered symbolic and numeric kernels.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

function DocLink({ icon: Icon, label }) {
  return (
    <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-white/60 hover:bg-white/5 hover:text-white transition-all text-sm">
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );
}

function FeatureCard({ title, description }) {
  return (
    <div className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:border-white/20 transition-all">
      <div className="w-8 h-8 bg-white/10 rounded-lg mb-4 flex items-center justify-center">
        <Activity className="w-4 h-4 text-white" />
      </div>
      <h4 className="font-bold mb-2">{title}</h4>
      <p className="text-white/40 text-sm leading-relaxed">{description}</p>
    </div>
  );
}
