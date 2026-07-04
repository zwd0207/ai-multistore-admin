const tones = {
  正常: 'success',
  正常运营: 'success',
  已完成: 'success',
  完成: 'success',
  成功: 'success',
  已处理: 'success',
  备份可用: 'success',
  低风险: 'success',
  성공: 'success',
  완료: 'success',

  处理中: 'info',
  待发货: 'info',
  已发货: 'info',
  配送中: 'info',
  已计划: 'info',
  已跳过: 'info',
  中风险: 'info',
  처리중: 'info',
  배송중: 'info',

  警告: 'warning',
  需要复核: 'warning',
  大小不一致: 'warning',
  需复核: 'warning',
  等待处理: 'warning',
  等待批准: 'warning',
  已阻断: 'warning',
  已回滚: 'warning',
  高风险: 'warning',
  경고: 'warning',

  失败: 'danger',
  '失败，需要处理': 'danger',
  紧急: 'danger',
  风险: 'danger',
  备份文件缺失: 'danger',
  已取消: 'danger',
  取消请求: 'danger',
  退货请求: 'danger',
  换货请求: 'danger',
  실패: 'danger',

  待确认: 'neutral',
  未知: 'neutral',
  暂无: 'neutral',
  演示数据: 'neutral',
};

export default function StatusBadge({ value }) {
  return <span className={`status-badge ${tones[value] || 'neutral'}`}><i />{value}</span>;
}
