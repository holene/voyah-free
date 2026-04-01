// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
	integrations: [
		starlight({
			title: 'Voyah Free Docs',
			defaultLocale: 'root',
			locales: {
				root: {
					label: 'English',
					lang: 'en',
				},
				no: {
					label: 'Norsk',
					lang: 'no',
				},
			},
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/withastro/starlight' },
			],
			sidebar: [
				{
					label: 'Overview',
					autogenerate: { directory: 'overview' },
				},
				{
					label: 'Technical',
					autogenerate: { directory: 'technical' },
				},
				{
					label: 'Triplescreen',
					autogenerate: { directory: 'triplescreen' },
				},
				{
					label: 'From PDF sources',
					autogenerate: { directory: 'from-sources' },
				},
			],
		}),
	],
});
