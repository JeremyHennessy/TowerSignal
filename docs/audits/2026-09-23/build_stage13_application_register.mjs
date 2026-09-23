import ts from 'typescript'
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

const root=process.cwd()
const srcRoot=path.join(root,'src')
const output='.audit-stage13'
fs.mkdirSync(output,{recursive:true})

const files=[]
function walk(dir){
  for(const entry of fs.readdirSync(dir,{withFileTypes:true})){
    const p=path.join(dir,entry.name)
    if(entry.isDirectory()) walk(p)
    else if(/\.(tsx|ts)$/.test(entry.name) && !/\.test\./.test(entry.name)) files.push(p)
  }
}
walk(srcRoot)

function rel(p){return path.relative(root,p).replaceAll('\\','/')}
function sourceFile(p){
  const text=fs.readFileSync(p,'utf8')
  return ts.createSourceFile(p,text,ts.ScriptTarget.Latest,true,p.endsWith('.tsx')?ts.ScriptKind.TSX:ts.ScriptKind.TS)
}
function line(sf,pos){return sf.getLineAndCharacterOfPosition(pos).line+1}
function textOf(sf,node){return node.getText(sf).replace(/\s+/g,' ').trim()}
function propChain(node){
  if(ts.isIdentifier(node)) return node.text
  if(ts.isPropertyAccessExpression(node)){
    const left=propChain(node.expression)
    return left?left+'.'+node.name.text:node.name.text
  }
  if(ts.isElementAccessExpression(node) && node.argumentExpression){
    const left=propChain(node.expression)
    if(ts.isStringLiteralLike(node.argumentExpression)) return (left?left+'.':'')+node.argumentExpression.text
  }
  return null
}
function chainsWithin(node){
  const chains=[]
  function visit(n){
    if(ts.isPropertyAccessExpression(n)){
      const parent=n.parent
      // only maximal chain; nested nodes appear within a larger property access.
      if(!ts.isPropertyAccessExpression(parent) || parent.expression!==n){
        const c=propChain(n);if(c)chains.push(c)
      }
    } else if(ts.isElementAccessExpression(n)){
      const parent=n.parent
      if(!ts.isPropertyAccessExpression(parent) && !ts.isElementAccessExpression(parent)){
        const c=propChain(n);if(c)chains.push(c)
      }
    }
    ts.forEachChild(n,visit)
  }
  visit(node)
  return [...new Set(chains)]
}
function nearestLabel(node,sf){
  let p=node.parent
  while(p){
    if(ts.isJsxElement(p)){
      const open=p.openingElement.tagName.getText(sf)
      // For dd, find sibling dt text.
      if(open==='dd'){
        const parent=p.parent
        if(parent && ts.isJsxElement(parent)){
          for(const child of parent.children){
            if(child===p)break
            if(ts.isJsxElement(child) && child.openingElement.tagName.getText(sf)==='dt'){
              const t=child.children.map(x=>textOf(sf,x)).join(' ').replace(/[{}]/g,'').trim()
              if(t)return t
            }
          }
        }
      }
      const literal=p.children.filter(ts.isJsxText).map(x=>x.text.trim()).filter(Boolean).join(' ')
      if(literal)return literal.slice(0,200)
    }
    p=p.parent
  }
  return null
}
function routeHints(text){
  return [...new Set([...text.matchAll(/#\/([A-Za-z0-9_?=/&.-]*)/g)].map(m=>'#/'+m[1]))]
}

const records=[]
for(const p of files){
  const sf=sourceFile(p);const file=rel(p);const fileText=sf.text;const hints=routeHints(fileText)
  function visit(n){
    if(ts.isJsxExpression(n) && n.expression){
      const parent=n.parent
      let kind='JSX_CHILD_EXPRESSION'
      let attribute=null
      if(ts.isJsxAttribute(parent)){
        kind='JSX_ATTRIBUTE_EXPRESSION';attribute=parent.name.getText(sf)
      }
      const expr=textOf(sf,n.expression)
      const chains=chainsWithin(n.expression)
      // Ignore event-handler-only attributes from application-field denominator.
      const eventOnly=kind==='JSX_ATTRIBUTE_EXPRESSION' && attribute && /^on[A-Z]/.test(attribute)
      if(!eventOnly){
        records.push({
          application_field_id:crypto.createHash('sha256').update(file+'|'+n.pos+'|'+expr).digest('hex').slice(0,20),
          field_kind:kind,
          file,line:line(sf,n.getStart(sf)),route_hints:hints,label:nearestLabel(n,sf),
          attribute,expression:expr,property_chains:chains,
          conditional_visibility:/&&|\?|\bif\b/.test(expr),
          verification:'STATIC_CURRENT_RUNTIME_AST',
          boundary:'Expression inventory; static presence does not prove the state was visually rendered or that every property chain is source-derived.'
        })
      }
    }
    ts.forEachChild(n,visit)
  }
  visit(sf)
}

// Non-TSX export/report object fields: explicit object-property values in files that produce reports/exports.
const exportFiles=files.filter(p=>/(Report|report|Export|export|prepareAccount|workflowExport)/.test(path.basename(p)))
const exports=[]
for(const p of exportFiles){
  const sf=sourceFile(p);const file=rel(p)
  function visit(n){
    if(ts.isPropertyAssignment(n) && !ts.isJsxAttribute(n.parent)){
      const name=textOf(sf,n.name)
      const expr=textOf(sf,n.initializer)
      const chains=chainsWithin(n.initializer)
      if(chains.length){
        exports.push({
          application_field_id:crypto.createHash('sha256').update('EXPORT|'+file+'|'+n.pos+'|'+name).digest('hex').slice(0,20),
          field_kind:'REPORT_OR_EXPORT_OBJECT_FIELD',file,line:line(sf,n.getStart(sf)),route_hints:routeHints(sf.text),
          label:name,attribute:null,expression:expr,property_chains:chains,conditional_visibility:false,
          verification:'STATIC_CURRENT_RUNTIME_AST',
          boundary:'Report/export mapping expression; generation correctness and rendered PDF/CSV acceptance are separate.'
        })
      }
    }
    ts.forEachChild(n,visit)
  }
  visit(sf)
}

const all=[...records,...exports]
const unique=[]
const seen=new Set()
for(const r of all){
  const key=[r.field_kind,r.file,r.line,r.label||'',r.expression].join('|')
  if(seen.has(key))continue;seen.add(key);unique.push(r)
}

// Reference prior verified normalized-source mappings where the terminal property name is known.
let normalizedMap=[]
const stage6='docs/audits/2026-09-23/stage6-consumer-lineage/core-normalized-consumer-lineage.json'
if(fs.existsSync(stage6)) normalizedMap=JSON.parse(fs.readFileSync(stage6,'utf8'))
const byNormalized=new Map()
for(const m of normalizedMap){
  if(!byNormalized.has(m.normalized_field))byNormalized.set(m.normalized_field,[])
  byNormalized.get(m.normalized_field).push({source_field:m.source_field,normalizer_file:m.normalizer_file,function:m.function})
}
for(const r of unique){
  const candidates=[]
  for(const chain of r.property_chains){
    const terminal=chain.split('.').at(-1)
    for(const m of byNormalized.get(terminal)||[]) candidates.push({...m,matched_property_chain:chain})
  }
  r.source_lineage_candidates=[...new Map(candidates.map(x=>[JSON.stringify(x),x])).values()]
  r.lineage_status=r.source_lineage_candidates.length?'SOURCE_NORMALIZED_NAME_CANDIDATE_REQUIRES_PATH_CONFIRMATION':'NO_DIRECT_SOURCE_MAPPING_FROM_CORE_NORMALIZED_MAP'
}

// Current route literal inventory and component import edges.
const routeInventory=[]
for(const p of files){
  const sf=sourceFile(p);const hints=routeHints(sf.text)
  if(hints.length) routeInventory.push({file:rel(p),routes:hints})
}
const importEdges=[]
for(const p of files){
  const sf=sourceFile(p)
  for(const st of sf.statements){
    if(ts.isImportDeclaration(st) && st.importClause && ts.isStringLiteral(st.moduleSpecifier)){
      const mod=st.moduleSpecifier.text
      if(mod.startsWith('.')) importEdges.push({from:rel(p),module:mod,names:st.importClause.namedBindings?textOf(sf,st.importClause.namedBindings):st.importClause.name?.text||null})
    }
  }
}

const summary={
  runtime_source_files:files.length,
  jsx_expression_fields:records.length,
  report_export_fields:exports.length,
  deduplicated_application_expression_records:unique.length,
  records_with_direct_core_source_name_candidates:unique.filter(x=>x.source_lineage_candidates.length).length,
  records_without_direct_core_source_name_candidates:unique.filter(x=>!x.source_lineage_candidates.length).length,
  route_literal_files:routeInventory.length,
  route_literals:[...new Set(routeInventory.flatMap(x=>x.routes))].sort(),
  denominator_definition:'Unique current-runtime JSX expression sites excluding event handlers plus explicit report/export object-field mappings. This is an application-expression denominator, not a claim that each expression is a distinct business concept.',
  verification_boundary:'Every record is individually inventoried with component/file/line/expression. Hosted state/rendering and backward source meaning require separate per-record statuses.'
}
fs.writeFileSync(output+'/application-field-register.json',JSON.stringify(unique,null,2))
fs.writeFileSync(output+'/application-field-summary.json',JSON.stringify(summary,null,2))
fs.writeFileSync(output+'/route-inventory.json',JSON.stringify(routeInventory,null,2))
fs.writeFileSync(output+'/component-import-edges.json',JSON.stringify(importEdges,null,2))
console.log(JSON.stringify(summary,null,2))
