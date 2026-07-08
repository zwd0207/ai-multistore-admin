import assert from 'node:assert/strict';
import {
  classifyCoreDataSource,
  getCoreApiCapability,
  getDangerousActionState,
} from '../src/utils/coreErpContract.js';

assert.equal(
  classifyCoreDataSource({ source_type: 'naver_real_order_sync' }).label,
  '读取自本地保存记录',
);

assert.equal(
  classifyCoreDataSource({ sourceType: 'shipping_mock_order' }).label,
  '演示数据',
);

assert.equal(
  classifyCoreDataSource({ localAssistant: true }).label,
  '本地辅助功能',
);

assert.equal(
  getCoreApiCapability('naver', 'order_read').category,
  'A',
);

assert.equal(
  getCoreApiCapability('naver', 'shipment_writeback').currentPhase,
  '本阶段关闭',
);

assert.equal(
  getCoreApiCapability('gmarket', 'appeal_submit').category,
  'C',
);

assert.deepEqual(
  getDangerousActionState('platform_inventory_write'),
  {
    enabled: false,
    label: '暂未开放',
    note: '平台写入动作本阶段保持关闭，必须单独审批后才能开启。',
  },
);

console.log('core ERP contract checks passed');
