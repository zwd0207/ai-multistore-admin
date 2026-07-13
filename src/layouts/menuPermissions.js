export function filterMenuGroupsForStore(menuGroups, selectedStoreId, canAccessStore) {
  if (!selectedStoreId) return [];

  return menuGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => !item[3] || canAccessStore(selectedStoreId, item[3])),
    }))
    .filter((group) => group.items.length);
}
