import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const root=path.dirname(fileURLToPath(import.meta.url));
const output=path.resolve(root,'../../outputs/comparaison-reprises');
const preview=path.join(root,'workbook-preview');
await fs.mkdir(preview,{recursive:true});
const read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const d=await read(path.join(output,'RESULTATS.json'));
const audit=await read(path.join(output,'AUDIT-FOREST.json'));
const previous=await read(path.join(output,'../comparaison-references/AUDIT-FOREST.json'));
const history=await read(path.join(output,'ESSAIS-FOREST.json'));
const old=new Map(previous.campaigns.filter(c=>c.trees_selected).map(c=>[c.case_id,c]));
const wb=Workbook.create();
const sheets=Object.fromEntries(['Comparaison','Forest','Arbres','Essais','Mesures'].map(n=>[n,wb.worksheets.add(n)]));
const palette={ink:'#23314A',muted:'#657087',pub:'#FFF1D2',ref:'#E4EEFC',forest:'#E3F2E9',rule:'#DCE2EA',head:'#243C62'};
function col(i){let s='';for(i++;i;i=Math.floor((i-1)/26))s=String.fromCharCode(65+(i-1)%26)+s;return s;}
function table(sheet,title,headers,rows,widths,header=5,name=''){
 const end=header+rows.length,last=col(headers.length-1);
 sheet.showGridLines=false;
 const all=sheet.getRange(`A${header===5?1:header}:${last}${end}`);
 all.format.font={name:'Arial',size:10,color:palette.ink};
 all.format.verticalAlignment='center';all.format.rowHeight=25;
 if(header===5){
  sheet.getRange('A2').values=[[title]];sheet.getRange('A2').format.font={size:14,bold:true};
  sheet.getRange(`A3:${last}3`).format.borders={bottom:{style:'thin',color:palette.rule}};
  sheet.freezePanes.freezeRows(header);sheet.freezePanes.freezeColumns(1);
 }
 sheet.getRange(`A${header}:${last}${header}`).values=[headers];
 sheet.getRange(`A${header}:${last}${header}`).format={fill:palette.head,font:{bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:46};
 if(rows.length)sheet.getRange(`A${header+1}:${last}${end}`).values=rows.map(r=>r.map(v=>v??null));
 for(let i=0;i<headers.length;i++)sheet.getRange(`${col(i)}1:${col(i)}${end}`).format.columnWidth=widths[i]||18;
 sheet.tables.add(`A${header}:${last}${end}`,true,name||title.replace(/[^a-zA-Z0-9]/g,'')+'Table').style='TableStyleLight1';
 return end;
}
const agg=d.rows.map(r=>[r.id,r.label,r.n,r.threads,r.aggregation,...['baseline','reference','old_selected','new_selected','old_g','new_g'].map(k=>r[k]?.seconds==null?null:r[k].seconds*1000),r.baseline?.count,r.published_hardware,r.hardware,r.compiler,r.source,r.notes]);
const end=table(sheets.Mesures,'Temps agrégés et données de mesure',
 ['ID documentaire','Programme / entrée','Taille n','Cœurs','Agrégation','Naïf (ms)','Référence (ms)','Ancien (ms)','Nouveau (ms)','Ancien G (ms)','Nouveau G (ms)','Blocs','Matériel publié','Matériel ROMEO','Compilateur','Source primaire','Adaptations et limites'],agg,
 [25,55,14,10,14,18,18,18,18,18,18,10,60,50,70,80,110]);
sheets.Mesures.getRange(`F6:K${end}`).setNumberFormat('0.000000');
sheets.Mesures.getRange('A4').values=[['Les agrégats proviennent des blocs bruts ci-dessous. Médiane, sauf UTF-8 BEST=min et MEAN=moyenne.']];
sheets.Mesures.getRange('A4').format.font={color:palette.muted,italic:true};
const rawStart=end+7;
sheets.Mesures.getRange(`A${rawStart-2}`).values=[['Mesures brutes — une ligne par exécution']];
sheets.Mesures.getRange(`A${rawStart-2}`).format.font={bold:true,size:12};
const rawEnd=table(sheets.Mesures,'Mesures brutes',
 ['Groupe','Programme','Variante','Bloc','Diagnostic','Taille n','Cœurs','Graine','Motif','Secondes','Correct','Code sortie','SHA256 entrée','Erreur absolue max','RMSE','Erreur'],
 d.measurements.map(r=>[r.group,r.case_id,r.variant,r.block,r.diagnostic,r.n,r.threads,r.seed,r.pattern,r.seconds,r.correct,r.exit_code,r.input_sha256,r.max_abs_error,r.rmse,r.error]),
 [],rawStart,'MesuresBrutes');
// Preserve widths chosen for the aggregate table; long fields remain accessible without wrapping all raw rows.
for(const [i,width] of [38,55,20,10,16,18,18,18,18,18,18,10,70,50,70,80,110].entries())sheets.Mesures.getRange(`${col(i)}1:${col(i)}${rawEnd}`).format.columnWidth=width;
sheets.Mesures.getRange(`B6:B${end}`).format.wrapText=true;
sheets.Mesures.getRange(`A6:Q${end}`).format.rowHeight=38;
sheets.Mesures.getRange(`D6:E${end}`).format.horizontalAlignment='center';
sheets.Mesures.getRange(`J${rawStart+1}:J${rawEnd}`).setNumberFormat('0.000000000');
sheets.Mesures.getRange(`N${rawStart+1}:O${rawEnd}`).setNumberFormat('0.000E+00');

const mainEnd=table(sheets.Comparaison,'Forest : reprises sur ROMEO',
 ['Programme / entrée','Publié','Réf. ROMEO ancienne','Réf. ROMEO actuelle','Forest ancien historique','Ancien remesuré','Nouveau remesuré','Nouveau / ancien','Nouveau / référence','Constat par blocs'],
 d.rows.map(r=>[r.label,r.published_speedup,r.previous_reference_speedup,null,r.previous_forest_speedup,null,null,null,null,r.verdict]),
 [52,13,17,17,18,17,17,17,18,46]);
sheets.Comparaison.tabColor=palette.head;
sheets.Comparaison.getRange(`A6:A${mainEnd}`).format.wrapText=true;
sheets.Comparaison.getRange(`A6:J${mainEnd}`).format.rowHeight=38;
sheets.Comparaison.getRange('A4').values=[['Speedup = naïf / variante. Ancien et nouveau remesurés dans une même allocation ROMEO.']];
sheets.Comparaison.getRange('A4').format.font={italic:true,color:palette.muted};
for(let i=0;i<d.rows.length;i++){
 const n=i+6;
 sheets.Comparaison.getRange(`D${n}`).formulas=[[`='Mesures'!F${n}/'Mesures'!G${n}`]];
 sheets.Comparaison.getRange(`F${n}:I${n}`).formulas=[[
  `='Mesures'!F${n}/'Mesures'!H${n}`,`='Mesures'!F${n}/'Mesures'!I${n}`,
  `='Mesures'!H${n}/'Mesures'!I${n}`,`='Mesures'!G${n}/'Mesures'!I${n}`]];
}
sheets.Comparaison.getRange(`B6:I${mainEnd}`).setNumberFormat('0.00"×"');
sheets.Comparaison.getRange(`H6:I${mainEnd}`).setNumberFormat('0.0000"×"');
sheets.Comparaison.getRange(`B6:B${mainEnd}`).format.fill=palette.pub;
sheets.Comparaison.getRange(`D6:D${mainEnd}`).format.fill=palette.ref;
sheets.Comparaison.getRange(`G6:G${mainEnd}`).format.fill=palette.forest;
sheets.Comparaison.getRange(`H6:I${mainEnd}`).conditionalFormats.add('cellIs',{operator:'greaterThan',formula:1,format:{font:{color:'#147144',bold:true}}});
sheets.Comparaison.getRange(`H6:I${mainEnd}`).conditionalFormats.add('cellIs',{operator:'lessThan',formula:1,format:{font:{color:'#A33A36'}}});
const notes=[
 '14 familles / 35 lignes documentaires ; plusieurs lignes partagent un même programme. Pas de moyenne globale de speedups.',
 'Une campagne finale par programme : cible de 2 h, contexte de 64 000 caractères, mémoire neuve ; tentatives remplacées conservées.',
 'Un rapport >1 dans Nouveau / ancien signifie que le nouveau code est plus rapide. Les deux temps viennent des mêmes blocs ROMEO.',
 'Les constats par blocs sont descriptifs, pas des tests de significativité ni des intervalles de confiance.',
 'Un code ou binaire identique entre ancien et nouveau est signalé ; ses écarts de temps ne sont pas comptés comme un gain.',
 'CPU : 7 blocs ; GPU : 9 blocs ; rendus : 3 blocs. Ordre pseudo-aléatoire, processus distinct par variante, échauffements conservés.',
 'Le matériel, les compilateurs, les entrées et les protocoles diffèrent aussi des publications. Aucun facteur de correction FLOPS.',
 'Les intégrations G, confirmées séparément, figurent ci-dessous. Le gagnant principal est fixé avant la comparaison finale.',
 'Sources et détails : Mesures et RAPPORT.md. Contextes, essais par arbre et erreurs : Forest, Arbres et AUDIT-FOREST.json.'
 ,'Black–Scholes 40 cœurs : forte variabilité confirmée sur 21 blocs supplémentaires. Voir STABILITE-BLACKSCHOLES.json.'
];
const noteStart=mainEnd+3;
for(let i=0;i<notes.length;i++){
 sheets.Comparaison.getRange(`A${noteStart+i}`).values=[[notes[i]]];
 sheets.Comparaison.getRange(`A${noteStart+i}`).format.font={name:'Arial',size:10,color:palette.muted};
}
const gHeader=noteStart+notes.length+3;
const gEnd=table(sheets.Comparaison,'Intégration G et étendues observées',
 ['Programme / entrée','Ancien G','Nouveau G','Ratio min nouveau/ancien','Ratio max nouveau/ancien','Variation speedup','Réduction du temps'],
 d.rows.map(r=>[r.label,null,null,...r.new_vs_old_range,null,null]),[],gHeader,'IntegrationEtEtendues');
for(let i=0;i<d.rows.length;i++){
 const n=i+6,k=i+gHeader+1,r=d.rows[i];
 for(const [target,source,key] of [['B','J','old_g'],['C','K','new_g']]){
  const cell=sheets.Comparaison.getRange(`${target}${k}`);
  if(r[key])cell.formulas=[[`='Mesures'!F${n}/'Mesures'!${source}${n}`]];
  else cell.values=[['n.a.']];
 }
 sheets.Comparaison.getRange(`F${k}:G${k}`).formulas=[[`=H${n}-1`,`=1-'Mesures'!I${n}/'Mesures'!H${n}`]];
}
for(const [i,width] of [52,13,17,17,18,17,17,17,18,46].entries())sheets.Comparaison.getRange(`${col(i)}1:${col(i)}${gEnd}`).format.columnWidth=width;
sheets.Comparaison.getRange(`B${gHeader+1}:E${gEnd}`).setNumberFormat('0.00"×"');
sheets.Comparaison.getRange(`D${gHeader+1}:E${gEnd}`).setNumberFormat('0.0000"×"');
sheets.Comparaison.getRange(`F${gHeader+1}:G${gEnd}`).setNumberFormat('0.0%');
sheets.Comparaison.getRange(`A${gHeader+1}:A${gEnd}`).format.wrapText=true;
sheets.Comparaison.getRange(`A${gHeader+1}:G${gEnd}`).format.rowHeight=38;

const forestEnd=table(sheets.Forest,'Moteur : avant et après',
 ['Programme','Job ancien','Job nouveau','Arbres avant','Arbres après','Essais avant','Essais après','G après','Valides','Incorrects','Génération échouée','Infra','Profondeur max','Durée SLURM (min)','Pipeline achevé','G confirmé','Appels natifs','Mother persistants','Appels éphémères','Session neuve','Erreur pipeline','Tous les statuts'],
 audit.campaigns.map(c=>{const o=old.get(c.case_id);return [c.case_id,o.job_id,c.job_id,o.trees_selected,c.trees_selected,Object.values(o.trial_counts).reduce((a,b)=>a+b,0),Object.values(c.trial_counts).reduce((a,b)=>a+b,0),c.trial_counts.G||0,...['valid','incorrect','generation_failed','infrastructure_error'].map(s=>c.trial_statuses[s]||0),Math.max(0,...c.tree_details.map(t=>t.max_mission_depth)),c.slurm_elapsed_seconds==null?null:c.slurm_elapsed_seconds/60,c.pipeline_complete,c.final_g_status==='confirmed',c.invocation_count,c.persistent_invocations,c.ephemeral_invocations,c.session_id,c.pipeline_error,JSON.stringify(c.trial_statuses)];}),
 [22,15,15,14,14,14,14,12,12,12,16,12,16,20,18,18,16,20,18,40,100,95]);
sheets.Forest.getRange(`N6:N${forestEnd}`).setNumberFormat('0.0');
sheets.Forest.getRange('A4').values=[['Essais = nœuds d’expérience enregistrés, G compris ; les lectures mémoire ne sont pas des essais.']];
sheets.Forest.getRange('A4').format.font={italic:true,color:palette.muted};
const forestNotes=[
 'Chaque programme repart avec zéro essai, zéro document et une nouvelle conversation Mother. Aucun candidat ancien importé.',
 'La mémoire continue entre essais du même programme. Les arbres ne sont donc pas tous amnésiques : leur mémoire appartient à ce programme.',
 'Contrôleur, compilation, validation et chronométrage : ROMEO. Relais : ordinateur local. Inférence du modèle : service hébergé.',
 'Modèle gpt-6-luna, effort max, graine 23, TreeQuest 0.3.2, méthode H, Mother persistante, memory-guided-v1, finish-started.',
 'Validation détaillée du moteur et 68 précontrôles : voir RAPPORT.md. Infrastructure, contexte et durée changent ensemble.',
 'La campagne finale Base64 ajoute le correctif de classement des réponses tronquées ; les 13 autres gardent leur moteur figé.'
];
sheets.Forest.getRange(`A${forestEnd+3}:A${forestEnd+2+forestNotes.length}`).values=forestNotes.map(v=>[v]);
sheets.Forest.getRange(`A${forestEnd+3}:A${forestEnd+2+forestNotes.length}`).format.font={name:'Arial',size:10,color:palette.muted};
const treeRows=[];
for(const c of audit.campaigns)for(const [period,run] of [['Ancien',old.get(c.case_id)],['Nouveau',c]])for(const t of run.tree_details){
 treeRows.push([c.case_id,period,run.job_id,t.role,t.subject,t.attempts,t.max_mission_depth,t.nonbaseline_parent_attempts,...['valid','incorrect','generation_failed','infrastructure_error'].map(s=>t.statuses[s]||0),t.objective,JSON.stringify(t.statuses)]);
}
const treeEnd=table(sheets.Arbres,'Chaque arbre et son exploration',
 ['Programme','Période','Job','Rôle','Sujet choisi par Mother','Essais','Profondeur max','Parents non naïfs','Valides','Incorrects','Génération échouée','Infra','Objectif','Tous les statuts'],treeRows,
 [22,15,15,10,80,12,16,18,12,12,20,12,140,80]);
sheets.Arbres.getRange('A4').values=[['T1 ancien et T1 nouveau peuvent viser des sujets différents ; comparer les objectifs.']];
sheets.Arbres.getRange('A4').format.font={italic:true,color:palette.muted};
sheets.Arbres.getRange(`E6:E${treeEnd}`).format.wrapText=true;
sheets.Arbres.getRange(`A6:N${treeEnd}`).format.rowHeight=42;

const trialEnd=table(sheets.Essais,'Historique de chaque essai',
 ['Programme','Période','Job','Ordre','Rôle','ID essai','Profondeur','Parent','Phase','Statut','Objectif (s)','Speedup exploration','Soumission (min)','Validation (min)','Commit','Hypothèse','Transformations','Diagnostic'],
 history.trials.map(t=>[t.case_id,t.period,t.job,t.ordinal,t.role,t.id,t.depth,t.parent_id,t.phase,t.status,t.mean_seconds,t.search_speedup,t.submitted_minute,t.settled_minute,t.commit,t.hypothesis,JSON.stringify(t.transformations),t.reason]),
 [22,15,15,10,10,22,14,24,18,23,20,22,20,20,46,110,110,110]);
sheets.Essais.getRange('A4').values=[['Speedups d’exploration : objectif et naïf propres à chaque campagne ; ne pas les confondre avec la comparaison finale.']];
sheets.Essais.getRange('A4').format.font={italic:true,color:palette.muted};
sheets.Essais.getRange(`K6:K${trialEnd}`).setNumberFormat('0.000000000');
sheets.Essais.getRange(`L6:L${trialEnd}`).setNumberFormat('0.00"×"');
sheets.Essais.getRange(`M6:N${trialEnd}`).setNumberFormat('0.0');
sheets.Essais.getRange(`D6:E${trialEnd}`).format.horizontalAlignment='center';

wb.recalculate();
const inspections=[];
for(const [name,range] of [['Comparaison','A5:J10'],['Forest','A5:N9'],['Arbres','A5:L9'],['Essais','A5:N9'],['Mesures','A5:L9']]){
 inspections.push((await wb.inspect({kind:'region',sheetId:name,range,maxChars:6500,tableMaxRows:5,tableMaxCols:14})).ndjson);
}
await fs.writeFile(path.join(preview,'inspection.txt'),inspections.join('\n'));
// Compare every live formula output to independent Python calculations.
const calc=sheets.Comparaison.getRange(`B6:I${mainEnd}`).values;
for(let i=0;i<d.rows.length;i++){
 const r=d.rows[i],expected=[r.published_speedup,r.previous_reference_speedup,r.reference_speedup,r.previous_forest_speedup,r.old_selected_speedup,r.new_selected_speedup,r.new_vs_old,r.new_vs_reference];
 for(let j=0;j<expected.length;j++)if(expected[j]!=null && (typeof calc[i][j]!=='number' || !Number.isFinite(calc[i][j]) || Math.abs(calc[i][j]-expected[j])>1e-10*Math.max(1,Math.abs(expected[j]))))throw Error(`Ratio mismatch row ${i+6}, col ${j+2}`);
}
const secondary=sheets.Comparaison.getRange(`B${gHeader+1}:G${gEnd}`).values;
for(let i=0;i<d.rows.length;i++){
 const r=d.rows[i],expected=[r.old_g_speedup,r.new_g_speedup,...r.new_vs_old_range,r.change_percent/100,r.time_reduction_percent/100];
 for(let j=0;j<expected.length;j++)if(expected[j]!=null && (typeof secondary[i][j]!=='number' || !Number.isFinite(secondary[i][j]) || Math.abs(secondary[i][j]-expected[j])>1e-10*Math.max(1,Math.abs(expected[j]))))throw Error(`Secondary ratio mismatch row ${i+gHeader+1}, col ${j+2}`);
}
const errors=[];
for(const [name,range] of [['Comparaison',`A1:J${gEnd}`],['Forest',`A1:V${forestEnd}`],['Arbres',`A1:N${treeEnd}`],['Essais',`A1:R${trialEnd}`],['Mesures',`A1:Q${rawEnd}`]]){
 const values=sheets[name].getRange(range).values;
 values.forEach((row,i)=>row.forEach((v,j)=>{if(typeof v==='string' && /^#(REF!|DIV\/0!|VALUE!|NAME\?|NUM!|NULL!|SPILL!|CALC!|N\/A$)/.test(v))errors.push({sheet:name,row:i+1,column:j+1,value:v});}));
}
await fs.writeFile(path.join(preview,'errors.json'),JSON.stringify(errors,null,2));
if(errors.length)throw Error('Spreadsheet contains formula errors');
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(path.join(output,'COMPARAISON.xlsx'));
for(const [name,range] of [['Comparaison','A1:J13'],['Forest','A1:N11'],['Arbres','A1:L10'],['Essais','A1:N10'],['Mesures','A1:L11']]){
 const rendered=await wb.render({sheetName:name,range,scale:1.2,format:'png'});
 await fs.writeFile(path.join(preview,name+'.png'),new Uint8Array(await rendered.arrayBuffer()));
}
await fs.writeFile(path.join(preview,'validation.json'),JSON.stringify({rows:d.rows.length,raw_measurements:d.measurements.length,all_primary_ratios_match_independent_python:true,all_secondary_ratios_match_independent_python:true,rendered_sheets:Object.keys(sheets),native_excel_tested:false},null,2));
console.log(JSON.stringify({output:path.join(output,'COMPARAISON.xlsx'),comparisons:d.rows.length,measurements:d.measurements.length,treeRows:treeRows.length}));
