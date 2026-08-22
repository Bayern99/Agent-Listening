# 0004. Keep Music IR Strictly Descriptive without Direct Synthesis Bindings

We decided that `music-ir.json` must remain a pure, domain-aligned descriptive representation of acoustic and musical facts. It will not encode engine-specific class names, synthesis parameters, or rigid mapping rules. Downstream compilation into sound synthesis patterns and sound design structures is delegated entirely to downstream consumer agents and compilers.
