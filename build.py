import os, sys

from subprocess import Popen,PIPE,STDOUT

# Notarize workflow: https://developer.apple.com/documentation/xcode/notarizing_your_app_before_distribution/customizing_the_notarization_workflow?language=objc

# Check notarization: xcrun altool --notarization-history 0 -u "post@yanone.de" -p "@keychain:AppleDev_AppSpecificPassword de.Yanone.GlyphsAppSpeedPunkReporter"

flavour = sys.argv[-1]


_list = [
['Remove all resource forks', 'xattr -cr "Space Bar.glyphsReporter"', None, ''],
['Remove code signatues', 'rm -r "Space Bar.glyphsReporter/Contents/_CodeSignature"', None, '', True],
['Remove code signatues', 'rm -r "Space Bar.glyphsReporter/Contents/CodeResources"', None, '', True],
['Remove zip file', 'rm "Space Bar.glyphsReporter.notarize.zip"', None, '', True],
['Remove zip file', 'rm "Space Bar.glyphsReporter.ship.zip"', None, '', True],
['Sign outer package', 'codesign --deep -s "Jan Gerner" -f "Space Bar.glyphsReporter"', None, ''],
['Verify signature', 'codesign -dv --verbose=4 "Space Bar.glyphsReporter"', None, ''],
['Verify signature', 'codesign --verify --deep --strict --verbose=2 "Space Bar.glyphsReporter"', None, ''],

['ZIP it', 'ditto -c -k --rsrc "Space Bar.glyphsReporter" "Space Bar.glyphsReporter.notarize.zip"', None, ''],

['Notarize', 'xcrun altool --notarize-app --primary-bundle-id "de.Yanone.GlyphsAppSpaceBarReporter" --username "post@yanone.de" --password "@keychain:AppleDev_AppSpecificPassword de.Yanone.GlyphsAppSpeedPunkReporter" --file "Space Bar.glyphsReporter.notarize.zip"', None, ''],
]

for l in _list:

	mayFail = False
	alt = None
	excludeCondition = None
	if len(l) == 2:
		desc, cmd = l
	if len(l) == 3:
		desc, cmd, alt = l
	if len(l) == 4:
		desc, cmd, alt, excludeCondition = l
	if len(l) == 5:
		desc, cmd, alt, excludeCondition, mayFail = l


	if not excludeCondition or excludeCondition != flavour:

		print(desc, '...')

		out = Popen(cmd, stderr=STDOUT,stdout=PIPE, shell=True)
		output, exitcode = out.communicate()[0].decode(), out.returncode

		if exitcode != 0 and not mayFail:
			print(output)
			print()
			print(cmd)
			print()
			print('%s failed! See above.' % desc)
			print()
			if alt:
				print('Debugging output:')
				os.system(alt)
			sys.exit(1)

print('Done.')
print()
