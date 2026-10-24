import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';
const root=path.dirname(fileURLToPath(import.meta.url));
const out=process.argv[2]||path.join(root,'workbook-preview');
await fs.mkdir(out,{recursive:true});
const d=JSON.parse(await fs.readFile(path.join(root,'analysis.json'),'utf8'));
const wb=Workbook.create();
const sheets=Object.fromEntries(['Comparaison','Conditions','Mesures ROMEO','Diagnostics','Essais Forest','Moteur','Lecture'].map(n=>[n,wb.worksheets.add(n)]));
const palette={ink:'#23314A',muted:'#657087',pub:'#FFF1D2',ref:'#E4EEFC',forest:'#E3F2E9',rule:'#DCE2EA',head:'#243C62'};
function col(i){let s='';for(i++;i;i=Math.floor((i-1)/26))s=String.fromCharCode(65+(i-1)%26)+s;return s;}
function text(x){return x==null?'':typeof x==='string'?x:JSON.stringify(x);}
function table(sheet,title,headers,rows,widths,header=5){
  const end=header+rows.length,last=col(headers.length-1);
  sheet.showGridLines=false;
  const all=sheet.getRange(`A1:${last}${end}`);
  all.format.font={name:'Arial',size:10,color:palette.ink};
  all.format.verticalAlignment='center';all.format.rowHeight=23;
  sheet.getRange('A2').values=[[title]];sheet.getRange('A2').format.font={size:14,bold:true};
  sheet.getRange(`A3:${last}3`).format.borders={bottom:{style:'thin',color:palette.rule}};
  sheet.getRange(`A${header}:${last}${header}`).values=[headers];
  sheet.getRange(`A${header}:${last}${header}`).format={fill:palette.head,font:{bold:true,color:'#FFFFFF'},horizontalAlignment:'center',wrapText:true,rowHeight:32,borders:{insideVertical:{style:'thin',color:'#FFFFFF'}}};
  if(rows.length)sheet.getRange(`A${header+1}:${last}${end}`).values=rows.map(r=>r.map(v=>v??null));
  for(let i=0;i<headers.length;i++)sheet.getRange(`${col(i)}1:${col(i)}${end}`).format.columnWidth=widths[i]||18;
  for(let i=header+2;i<=end;i+=2)sheet.getRange(`A${i}:${last}${i}`).format.fill='#F5F7FA';
  sheet.freezePanes.freezeRows(header);sheet.freezePanes.freezeColumns(1);
  sheet.tables.add(`A${header}:${last}${end}`,true,title.replace(/[^a-zA-Z0-9]/g,'')+'Table').style='TableStyleLight1';
  return end;
}
const condHeaders=['ID','Programme / variante','Speedup publié retenu','Calcul publié','Annonce publiée','Naïf ROMEO (ms)','Référence ROMEO (ms)','Forest retenu (ms)','Forest G (ms)','Répétitions','Agrégation','Taille n','Cœurs max','Motif entrée','Matériel publié','Matériel ROMEO','Compilateurs ROMEO','Entrée publiée','Naïf mesuré','Référence mesurée','Limites et adaptations','Source primaire'];
const condRows=d.rows.map(r=>[r.id,r.label,r.published_speedup,r.published_computed_speedup,r.published_stated_speedup,...['baseline','reference','forest','final_g'].map(k=>r[k]?.seconds*1000||null),r.baseline?.count,r.aggregation,r.n,r.threads,r.pattern,r.published_hardware,r.hardware,r.compiler,r.published_input,r.baseline_variant,r.reference_variant,r.notes,r.source]);
table(sheets.Conditions,'Conditions et données de calcul',condHeaders,condRows,[34,65,18,18,18,20,22,22,22,16,16,16,16,16,55,48,65,60,20,22,110,80]);
sheets.Conditions.getRange('C6:E67').setNumberFormat('0.00"×"');
sheets.Conditions.getRange('F6:I67').setNumberFormat('0.000000');
sheets.Conditions.getRange('J6:N67').setNumberFormat('0');
// The output ratios point directly to the measured absolute times.
const mainRows=d.rows.map(r=>[r.label,null,null,null,null,r.forest_speedup==null?(r.case_id?'Mesure en cours':'Non reproduit'):r.engine?.naive_retained?'Naïf conservé (recherche en échec)':r.status.replace(' à chaque répétition','').replace(' ; naïf historique invalide hors texte valide','*')]);
const end=table(sheets.Comparaison,'Publié · ROMEO · Forest',['Programme / variante','Publié','Référence ROMEO','Forest sur ROMEO','Forest / référence','Constat sur les répétitions'],mainRows,[53,15,18,18,18,46]);
sheets.Comparaison.tabColor=palette.head;
sheets.Comparaison.getRange('A4').values=[['Speedup = temps du naïf / temps de la variante. Même naïf pour les deux colonnes ROMEO.']];
sheets.Comparaison.getRange('A4').format.font={size:10,italic:true,color:palette.muted};
for(let i=0;i<d.rows.length;i++){
 const r=d.rows[i],n=i+6;
 sheets.Comparaison.getRange(`B${n}`).formulas=[[`=Conditions!C${n}`]];
 if(r.forest_speedup!=null)sheets.Comparaison.getRange(`C${n}:E${n}`).formulas=[[`=Conditions!F${n}/Conditions!G${n}`,`=Conditions!F${n}/Conditions!H${n}`,`=Conditions!G${n}/Conditions!H${n}`]];
 else sheets.Comparaison.getRange(`C${n}:E${n}`).values=[[r.case_id?'…':'NR',r.case_id?'…':'NR',r.case_id?'…':'NR']];
}
sheets.Comparaison.getRange(`B6:E${end}`).setNumberFormat('0.00"×"');
sheets.Comparaison.getRange(`B6:B${end}`).format.fill=palette.pub;
sheets.Comparaison.getRange(`C6:C${end}`).format.fill=palette.ref;
sheets.Comparaison.getRange(`D6:D${end}`).format.fill=palette.forest;
sheets.Comparaison.getRange(`B6:E${end}`).format.horizontalAlignment='right';
sheets.Comparaison.getRange(`E6:E${end}`).conditionalFormats.add('cellIs',{operator:'greaterThan',formula:1,format:{font:{color:'#147144',bold:true}}});
sheets.Comparaison.getRange(`E6:E${end}`).conditionalFormats.add('cellIs',{operator:'lessThan',formula:1,format:{font:{color:'#A33A36'}}});
sheets.Comparaison.getRange('H5').values=[['À lire avec les chiffres']];sheets.Comparaison.getRange('H5').format.font={name:'Arial',size:10,bold:true};
const noteRows=[
 `${d.summary.measured}/62 observations mesurées ; ${d.summary.unavailable} sans source ou données suffisantes.`,
 '62 lignes documentaires : certaines partagent le même programme.',
 'Les changements de matériel, compilateur, source et protocole se cumulent.',
 'Aucune correction par les FLOPS théoriques n’a été appliquée.',
 'Forest / référence >1 : Forest est plus rapide sur ROMEO.',
 'CPU : 7 blocs ; GPU : 9 blocs ; rendus : 3 blocs.',
 'Rapport des médianes ; UTF-8 BEST=min, MEAN=moyenne des lots.',
 'Le meilleur confirmé est affiché ; l’intégration G est dans Conditions.',
 '* UTF-8 naïf historique incorrect sur certaines chaînes malformées.',
 'NR = non reproduit. Aucun temps manquant remplacé par zéro.',
 'Voir Lecture pour le protocole et Conditions pour chaque source.'
];
sheets.Comparaison.getRange('H6:H16').values=noteRows.map(v=>[v]);sheets.Comparaison.getRange('H5:H16').format.columnWidth=100;sheets.Comparaison.getRange('H6:H16').format.font={name:'Arial',size:10,color:palette.muted};sheets.Comparaison.getRange('G1:G67').format.columnWidth=3;
const rawHeaders=['Groupe','Cas','Variante','Bloc','Diagnostic','Taille n','Graine','Cœurs','Motif','Temps (ms)','Correct','Code sortie','Erreur absolue max','RMSE','SHA256 entrée','Erreur'];
table(sheets['Mesures ROMEO'],'Mesures finales sans sélection a posteriori',rawHeaders,d.measurements.map(r=>[r.group,r.case_id,r.variant,r.block,r.diagnostic,r.n,r.seed,r.threads,r.pattern,r.seconds==null?null:r.seconds*1000,r.correct,r.exit_code,r.max_abs_error,r.rmse,r.input_sha256,r.error]),[14,20,20,10,14,16,12,10,10,20,12,12,22,20,72,75]);
sheets['Mesures ROMEO'].getRange(`J6:J${d.measurements.length+5}`).setNumberFormat('0.000000');
sheets['Mesures ROMEO'].getRange(`M6:N${d.measurements.length+5}`).setNumberFormat('0.000E+00');
sheets['Mesures ROMEO'].getRange(`K6:K${d.measurements.length+5}`).conditionalFormats.add('cellIs',{operator:'equal',formula:'FALSE',format:{fill:'#FCE5E4',font:{color:'#A33A36',bold:true}}});
sheets['Mesures ROMEO'].getRange(`L6:L${d.measurements.length+5}`).conditionalFormats.add('cellIs',{operator:'notEqual',formula:0,format:{fill:'#FCE5E4',font:{color:'#A33A36',bold:true}}});
const diagnostics=[];
for(const r of d.utf8_audit?.records||[])diagnostics.push(['UTF-8',r.variant,'1/2 octets, frontières SIMD, aléatoire',r.cases,r.failed,null,'Texte valide et malformé','Décodeur Python strict ; graine 8231 ; 79 729 cas par version.']);
for(const r of d.volume_domain_audit?.records||[])diagnostics.push(['Volume',r.variant,`${r.width}×${r.height}`,1,r.measurement?.correct?0:1,r.measurement?.errors??null,r.reference_supported_domain?'Dans le domaine ISPC':'Hors domaine ISPC','ISPC exige des dimensions multiples de 4 ; zone de garde agrandie seulement pour cet audit, sans chronométrage.']);
table(sheets.Diagnostics,'Contrôles indépendants et domaines de validité',['Famille','Variante','Entrées','Cas testés','Échecs','Erreurs de sortie','Domaine du test','Protocole'],diagnostics,[16,20,45,16,14,20,28,115]);
sheets.Diagnostics.getRange(`E6:E${diagnostics.length+5}`).conditionalFormats.add('cellIs',{operator:'greaterThan',formula:0,format:{fill:'#FCE5E4',font:{color:'#A33A36',bold:true}}});
const trialHeaders=['Cas','Ordre enregistré','Rôle','ID essai','Statut','Moyenne objective (s)','Commit','Parent','Hypothèse déclarée','Transformations déclarées','Diagnostic'];
table(sheets['Essais Forest'],'Historique des essais Forest',trialHeaders,d.trials.map(r=>[r.case_id,r.ordinal,r.role,r.id,r.status,r.seconds,r.commit,r.parent,r.hypothesis,text(r.transformations),r.reason]),[20,17,12,22,22,24,46,46,120,120,100]);
sheets['Essais Forest'].getRange(`F6:F${d.trials.length+5}`).setNumberFormat('0.000000000');
const engineHeaders=['Cas','Job SLURM','Moteur achevé','Naïf conservé','Essais','Commit retenu','Commit G','G confirmé','Modèle','Effort','Cible (s)','Durée réelle (s)','Dépassement (s)','Erreur pipeline'];
table(sheets.Moteur,'Exécution du moteur et intégration finale',engineHeaders,d.engines.map(r=>[r.case_id,r.job,r.pipeline_complete,r.naive_retained,r.trial_count,r.selected_commit,r.final_g_commit,r.final_g_confirmed,r.model,r.effort,r.target_seconds,r.timing?.finished_at&&r.timing?.started_at?r.timing.finished_at-r.timing.started_at:null,r.timing?.overrun_seconds??null,r.error]),[20,18,18,18,12,46,46,18,22,14,14,20,20,100]);
sheets.Moteur.getRange(`K6:M${d.engines.length+5}`).setNumberFormat('0.0');
const lecture=[
 ['Périmètre',`${d.summary.observations} observations publiées, ${d.summary.engine_cases} familles de programmes exécutées. Cinq observations non reproduites sont détaillées dans Conditions.`],
 ['Ordre expérimental','Références naïves et optimisées sur ROMEO, puis recherche Forest démarrant du naïf, puis revalidation et rechronométrage commun de toutes les variantes. Les références optimisées sont cachées au modèle.'],
 ['Matériel CPU','AMD EPYC 9654, 2 sockets × 96 cœurs ; SMT désactivé. Sous-ensembles de 1, 4, 8 ou 40 cœurs physiques. Nœud partagé ; affinités et allocations consignées.'],
 ['Matériel GPU','NVIDIA GH200 120 Go sur Grace ARM ; CUDA 12.6.3, pilote 590.48.01. torch 2.9.1+cu126 et Triton 3.5.1 pour les cas concernés.'],
 ['Formules','Publié : annonce du tableau si disponible, sinon ratio calculé du tableau. Référence ROMEO = naïf ROMEO / référence ROMEO. Forest = même naïf ROMEO / candidat retenu. Forest / référence = temps référence / temps Forest.'],
 ['Répétitions','Sept blocs CPU, neuf blocs GPU, trois blocs rendus, ordre des variantes pseudo-aléatoire. Rapport des médianes ; UTF-8 BEST et MEAN conservent min et moyenne des lots. Les étendues par paire du dashboard ne sont pas des intervalles de confiance.'],
 ['Entrées','Mêmes tailles, précisions, graines et données entre variantes d’un bloc. Contrôles supplémentaires sur entrées indépendantes. Les sources et données historiques manquantes sont identifiées au lieu d’être inventées.'],
 ['Limite causale','Les différences entre publication et ROMEO reflètent aussi les compilateurs, versions de sources, entrées et protocoles. Elles ne mesurent pas isolément l’effet du matériel.'],
 ['Forest','Engine hpc-forest-r1 gelé, méthode H, TreeQuest AB-MCTS-A, Mother persistante, memory-guided-v1, graine 23, gpt-6-luna/max, cible 1800 s, finish-started. Un seul lancement par famille hors réparation d’un défaut d’import deferred avant tout appel modèle.'],
 ['Validation','Sorties complètes, oracles, entrées immuables, gardes mémoire ; tolérances documentées. AO est stochastique : RMSE et biais moyens, complétés par la revue du nombre de rayons. Aucun résultat ne constitue une preuve sur toutes les entrées possibles.'],
 ['UTF-8','Naïf historique : 5773 échecs sur 79729 cas stricts. Naïf corrigé, référence AVX, Forest et G : zéro sur cet audit. Les temps historiques concernent uniquement du texte valide.'],
 ['Volume ISPC','Les dimensions doivent être multiples de 4. Deux tests additionnels hors domaine ont planté ; dix contrôles dans le domaine passent. Les quatre tests avec gardes confirment les écritures hors image sur tailles non admissibles. Voir Diagnostics.'],
 ['Tailles et cœurs','Certaines lignes à 40 cœurs utilisent une entrée plus grande : AO 2048² au lieu de 512², options 2097152 au lieu de 131072 éléments. Ces lignes ne forment pas une étude de passage de 1 à 40 cœurs à taille constante.'],
 ['Erreurs moteur','Trois premières campagnes GPU ont terminé recherche/confirmation mais échoué à l’empaquetage (Makefile/run.sh manquants). Les sources retenues ont été remesurées indépendamment. Les erreurs de recherche Base64 et autres essais restent consignées.'],
 ['Coûts modèle','Les compteurs cumulés de conversations reprises peuvent être additionnés plusieurs fois dans les journaux natifs. Aucun total de tokens ni coût monétaire n’est présenté comme audité.'],
 ['Reproductibilité','Voir PREUVES-ET-CODES.zip : sources figées, scripts, résultats bruts, manifestes SHA256, archives des campagnes et diagnostics. Le classeur source original reste inchangé.'],
 ['Date','23 octobre 2026. Voir les horodatages UTC des mesures et les jobs SLURM pour la chronologie exacte.']
];
table(sheets.Lecture,'Lire cette comparaison',['Sujet','Convention et limites'],lecture,[24,140]);
sheets.Lecture.tabColor='#7D8795';sheets.Lecture.getRange(`B6:B${lecture.length+5}`).format.wrapText=true;sheets.Lecture.getRange(`A6:B${lecture.length+5}`).format.rowHeight=55;
wb.recalculate();
console.log((await wb.inspect({kind:'region',sheetId:'Comparaison',range:'A5:F10',maxChars:3500,tableMaxCols:6,tableMaxRows:6})).ndjson);
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(path.join(out,'COMPARAISON.xlsx'));
// A bounded render is enabled after checking the documented render options.
if(process.env.RENDER_RANGE==='1'){
 const preview=await wb.render({sheetName:'Comparaison',range:'A1:F16',scale:1.4,format:'png'});
 await fs.writeFile(path.join(out,'APERCU.png'),new Uint8Array(await preview.arrayBuffer()));
}
console.log(JSON.stringify({output:path.join(out,'COMPARAISON.xlsx'),observations:d.rows.length,measurements:d.measurements.length}));
