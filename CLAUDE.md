# CLAUDE.md

## Memoria persistente (MCP)

Este repo tiene instalado el servidor MCP oficial `@modelcontextprotocol/server-memory`
(entry `"memory"` en `.mcp.json`), un knowledge graph persistente (entidades/relaciones/
observaciones) para que Claude recuerde contexto entre sesiones.

- Storage: `.claude/memory/knowledge-graph.jsonl` (versionado en git, no en `/tmp`, para
  que sobreviva a reinicios del entorno).
- Usar `create_entities` / `create_relations` / `add_observations` para guardar contexto
  nuevo; `search_nodes` / `read_graph` antes de asumir que no hay contexto previo.
- Despues de escribir memoria nueva: `git add .claude/memory/` + commit, o se pierde al
  reciclar el contenedor.
- Para replicar en otro repo: copiar el bloque `"memory": {...}` a su `.mcp.json` y crear
  un `.claude/memory/knowledge-graph.jsonl` vacio.
