export function filterMenuGroupsForStore(menuGroups, selectedStoreId, canAccessStore) {
  return menuGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => (
        item[4] === false
        || (selectedStoreId && (!item[3] || canAccessStore(selectedStoreId, item[3])))
      )),
    }))
    .filter((group) => group.items.length);
}
