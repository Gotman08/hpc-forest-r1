export const HISTORY_PAGE_SIZES = [10, 25, 50];

export function historyPage(records, filter="", query="", page=1, pageSize=10) {
  const size=HISTORY_PAGE_SIZES.includes(pageSize)?pageSize:HISTORY_PAGE_SIZES[0];
  const search=query.trim().toLocaleLowerCase("fr");
  const matches=records.filter(r=>(!filter||r.state===filter)&&
    String(r.name??"").toLocaleLowerCase("fr").includes(search));
  const pages=Math.max(1,Math.ceil(matches.length/size));
  const current=Math.min(pages,Math.max(1,Number.isFinite(page)?Math.trunc(page):1));
  const offset=(current-1)*size;
  const numbers=[...new Set([1,current-1,current,current+1,pages])]
    .filter(n=>n>=1&&n<=pages).sort((a,b)=>a-b);
  return {rows:matches.slice(offset,offset+size),total:matches.length,page:current,pages,
    pageSize:size,start:matches.length?offset+1:0,end:Math.min(offset+size,matches.length),numbers};
}
