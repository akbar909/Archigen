import React, { useMemo, useState } from 'react';
import { Armchair } from 'lucide-react';
import fallbackCatalog from '../../catalog/furnitureCatalog.json';
export default function FurniturePaletteDrawer({
  assets = [],
  selected,
  onChoose
}) {
  const [search, setSearch] = useState(''),
    [category, setCategory] = useState('all');
  const catalog = useMemo(() => {
    const uploaded = assets.filter(a => a.kind === 'model' && ['furniture', ''].includes(a.group || '') && !a.wall_mounted && !a.ceiling_mounted && !['wall', 'ceiling', 'tabletop'].includes(a.mounting?.surface));
    return uploaded.length ? uploaded : fallbackCatalog;
  }, [assets]);
  const categories = [...new Set(catalog.map(a => a.category || 'other'))].sort();
  const filtered = catalog.filter(a => (category === 'all' || (a.category || 'other') === category) && `${a.name} ${a.category}`.toLowerCase().includes(search.toLowerCase()));
  return <div className="cad-palette"><p>Choose an asset, then tap a room to place it. You can also drag it onto the plan.</p><input aria-label="Search furniture" placeholder="Search furniture…" value={search} onChange={e => setSearch(e.target.value)} /><select aria-label="Furniture category" value={category} onChange={e => setCategory(e.target.value)}><option value="all">All categories</option>{categories.map(c => <option key={c} value={c}>{c.replaceAll('_', ' ')}</option>)}</select><div className="cad-assets">{filtered.map(a => <button key={a.id || a.asset_id} className={selected?.id === a.id ? 'active' : ''} draggable onDragStart={e => {
        e.dataTransfer.setData('application/archigen-asset', JSON.stringify(a));
        e.dataTransfer.effectAllowed = 'copy';
      }} onClick={() => onChoose(a)}><Armchair size={22} /><span>{a.name || a.id}<small>{a.category?.replaceAll('_', ' ')}</small></span></button>)}{!filtered.length && <p>No matching assets.</p>}</div></div>;
}
