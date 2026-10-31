// Only a complete observation for the still-visible mission may replace its view.
export function createMissionPoller({current, load, display, failed}) {
  let pending=false, lastError=null;
  const same = ticket => {
    const now=current();
    return now && now.id===ticket.id && now.navigation===ticket.navigation &&
      now.selection===ticket.selection && now.route===ticket.route;
  };
  return async () => {
    const ticket=current();
    if(pending||!ticket) return;
    pending=true;
    try {
      const mission=await load("/missions/"+ticket.id);
      if(!same(ticket)) return;
      const campaign=mission.campaign_id?await load("/campaigns/"+mission.campaign_id):null;
      if(!same(ticket)) return;
      display(mission,campaign);
      lastError=null;
    } catch(error) {
      if(same(ticket)&&lastError!==error.message) {
        lastError=error.message;
        failed(error);
      }
    } finally {
      pending=false;
    }
  };
}
